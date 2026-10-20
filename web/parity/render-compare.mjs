export function compareRgba(a, b, options = {}) {
  if (a.length !== b.length) {
    throw new Error(`size mismatch: ${a.length} bytes against ${b.length} bytes`);
  }
  const skipTopRows = options.skipTopRows || 0;
  let start = 0;
  if (skipTopRows !== 0) {
    if (!options.width) {
      throw new Error("skipTopRows needs the width");
    }
    const height = a.length / 4 / options.width;
    if (skipTopRows < 0 || skipTopRows >= height) {
      throw new Error(`skipTopRows ${skipTopRows} outside the image`);
    }
    start = skipTopRows * options.width * 4;
  }
  const pixels = (a.length - start) / 4;
  const histogram = {};
  let differingPixels = 0;
  let maxChannelDiff = 0;
  for (let i = start; i < a.length; i += 4) {
    const diff = Math.max(
      Math.abs(a[i] - b[i]),
      Math.abs(a[i + 1] - b[i + 1]),
      Math.abs(a[i + 2] - b[i + 2]),
      Math.abs(a[i + 3] - b[i + 3]),
    );
    histogram[diff] = (histogram[diff] || 0) + 1;
    if (diff > 0) {
      differingPixels += 1;
      if (diff > maxChannelDiff) {
        maxChannelDiff = diff;
      }
    }
  }
  return {
    pixels,
    differingPixels,
    maxChannelDiff,
    fraction: pixels === 0 ? 0 : differingPixels / pixels,
    histogram,
  };
}

export function exactRule() {
  return { maxChannelDiff: 0, maxFraction: 0 };
}

export function decide(metrics, rule) {
  if (!rule || typeof rule.maxChannelDiff !== "number" || typeof rule.maxFraction !== "number") {
    throw new Error("rule needs maxChannelDiff and maxFraction");
  }
  if (metrics.differingPixels === 0) {
    return { status: "identical" };
  }
  if (metrics.maxChannelDiff <= rule.maxChannelDiff && metrics.fraction <= rule.maxFraction) {
    return { status: "within_tolerance" };
  }
  return { status: "different" };
}

export const ROUNDING_LEVEL = 2;
const BLOCK = 16;
export const MAX_BLOCK_MEAN = 8;

function neighbourhoodRange(data, x, y, width, firstRow, lastRow, radius, channel) {
  let low = 255;
  let high = 0;
  for (let ny = Math.max(firstRow, y - radius); ny <= Math.min(lastRow, y + radius); ny += 1) {
    for (let nx = Math.max(0, x - radius); nx <= Math.min(width - 1, x + radius); nx += 1) {
      const value = data[(ny * width + nx) * 4 + channel];
      if (value < low) {
        low = value;
      }
      if (value > high) {
        high = value;
      }
    }
  }
  return [low, high];
}

function insideNeighbourhood(value, source, x, y, width, firstRow, lastRow, radius, channel) {
  const [low, high] = neighbourhoodRange(source, x, y, width, firstRow, lastRow, radius, channel);
  return value >= low - ROUNDING_LEVEL && value <= high + ROUNDING_LEVEL;
}

export function blockMeanDifference(a, b, options) {
  const { width, skipTopRows = 0, block = BLOCK } = options;
  const height = a.length / 4 / width;
  let worst = 0;
  for (let by = skipTopRows; by + block <= height; by += block) {
    for (let bx = 0; bx + block <= width; bx += block) {
      for (let c = 0; c < 4; c += 1) {
        let sum = 0;
        for (let y = by; y < by + block; y += 1) {
          for (let x = bx; x < bx + block; x += 1) {
            const i = (y * width + x) * 4 + c;
            sum += a[i] - b[i];
          }
        }
        const mean = Math.abs(sum) / (block * block);
        if (mean > worst) {
          worst = mean;
        }
      }
    }
  }
  return worst;
}

export function explainDifferences(a, b, options) {
  const { width, skipTopRows = 0, radius = 1, sample = 8 } = options;
  const height = a.length / 4 / width;
  const lastRow = height - 1;
  const result = {
    rounding: 0,
    coverage: 0,
    unexplained: 0,
    blockMean: blockMeanDifference(a, b, { width, skipTopRows }),
    box: null,
    samples: [],
  };
  for (let y = skipTopRows; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = (y * width + x) * 4;
      let level = 0;
      for (let c = 0; c < 4; c += 1) {
        level = Math.max(level, Math.abs(a[i + c] - b[i + c]));
      }
      if (level === 0) {
        continue;
      }
      if (level <= ROUNDING_LEVEL) {
        result.rounding += 1;
        continue;
      }
      let explained = true;
      for (let c = 0; c < 4 && explained; c += 1) {
        explained =
          insideNeighbourhood(a[i + c], b, x, y, width, skipTopRows, lastRow, radius, c) &&
          insideNeighbourhood(b[i + c], a, x, y, width, skipTopRows, lastRow, radius, c);
      }
      if (explained) {
        result.coverage += 1;
        continue;
      }
      result.unexplained += 1;
      if (result.box === null) {
        result.box = [x, y, x, y];
      } else {
        result.box = [Math.min(result.box[0], x), Math.min(result.box[1], y), Math.max(result.box[2], x), Math.max(result.box[3], y)];
      }
      if (result.samples.length < sample) {
        result.samples.push({ x, y, level, a: Array.from(a.slice(i, i + 4)), b: Array.from(b.slice(i, i + 4)) });
      }
    }
  }
  return result;
}

export function classify(metrics, explained) {
  if (metrics.differingPixels === 0) {
    return "identical";
  }
  if (explained.unexplained > 0 || explained.blockMean > MAX_BLOCK_MEAN) {
    return "structural";
  }
  return explained.coverage === 0 ? "rounding" : "edge";
}

const PASSING = new Set(["identical", "within_tolerance"]);

export function summarize(results) {
  const counts = {};
  for (const result of results) {
    counts[result.status] = (counts[result.status] || 0) + 1;
  }
  const failures = results.filter((result) => !PASSING.has(result.status));
  return {
    total: results.length,
    counts,
    failures,
    ok: results.length > 0 && failures.length === 0,
  };
}
