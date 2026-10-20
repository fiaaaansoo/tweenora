import assert from "node:assert/strict";
import { test } from "node:test";

import { MAX_BLOCK_MEAN, ROUNDING_LEVEL, blockMeanDifference, classify, compareRgba, decide, exactRule, explainDifferences, summarize } from "./render-compare.mjs";

function image(width, height, fill) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < width * height; i += 1) {
    data.set(fill, i * 4);
  }
  return data;
}

test("two identical images have no difference", () => {
  const a = image(4, 4, [10, 20, 30, 255]);
  const b = image(4, 4, [10, 20, 30, 255]);
  assert.deepEqual(compareRgba(a, b), {
    pixels: 16,
    differingPixels: 0,
    maxChannelDiff: 0,
    fraction: 0,
    histogram: { 0: 16 },
  });
});

test("one pixel off by three levels on one channel is counted once", () => {
  const a = image(4, 4, [10, 20, 30, 255]);
  const b = image(4, 4, [10, 20, 30, 255]);
  b[4 * 5 + 1] = 23;
  const result = compareRgba(a, b);
  assert.equal(result.differingPixels, 1);
  assert.equal(result.maxChannelDiff, 3);
  assert.equal(result.fraction, 1 / 16);
  assert.deepEqual(result.histogram, { 0: 15, 3: 1 });
});

test("the alpha channel counts", () => {
  const a = image(2, 2, [0, 0, 0, 255]);
  const b = image(2, 2, [0, 0, 0, 255]);
  b[3] = 250;
  assert.equal(compareRgba(a, b).maxChannelDiff, 5);
});

test("images of different sizes cannot be compared", () => {
  assert.throws(() => compareRgba(image(2, 2, [0, 0, 0, 255]), image(3, 2, [0, 0, 0, 255])), /size/);
});

test("the rows above skipTopRows are ignored and not counted", () => {
  const a = image(2, 4, [0, 0, 0, 255]);
  const b = image(2, 4, [0, 0, 0, 255]);
  b.set([255, 255, 255, 255], 0);
  b.set([9, 0, 0, 255], 4 * 2 * 2);
  const result = compareRgba(a, b, { width: 2, skipTopRows: 2 });
  assert.equal(result.pixels, 4);
  assert.equal(result.differingPixels, 1);
  assert.equal(result.maxChannelDiff, 9);
});

test("skipTopRows needs the width and must stay inside the image", () => {
  const a = image(2, 4, [0, 0, 0, 255]);
  assert.throws(() => compareRgba(a, a, { skipTopRows: 1 }), /width/);
  assert.throws(() => compareRgba(a, a, { width: 2, skipTopRows: 4 }), /skipTopRows/);
  assert.throws(() => compareRgba(a, a, { width: 2, skipTopRows: -1 }), /skipTopRows/);
});

test("the exact rule accepts only a zero difference", () => {
  assert.equal(decide({ differingPixels: 0, maxChannelDiff: 0, fraction: 0 }, exactRule()).status, "identical");
  assert.equal(decide({ differingPixels: 1, maxChannelDiff: 1, fraction: 0.001 }, exactRule()).status, "different");
});

test("a tolerance rule bounds both the channel level and the fraction of pixels", () => {
  const rule = { maxChannelDiff: 2, maxFraction: 0.01 };
  assert.equal(decide({ differingPixels: 5, maxChannelDiff: 2, fraction: 0.005 }, rule).status, "within_tolerance");
  assert.equal(decide({ differingPixels: 5, maxChannelDiff: 3, fraction: 0.005 }, rule).status, "different");
  assert.equal(decide({ differingPixels: 500, maxChannelDiff: 2, fraction: 0.02 }, rule).status, "different");
  assert.equal(decide({ differingPixels: 0, maxChannelDiff: 0, fraction: 0 }, rule).status, "identical");
});

test("a tolerance rule must have both bounds", () => {
  assert.throws(() => decide({ differingPixels: 1, maxChannelDiff: 1, fraction: 0.1 }, { maxChannelDiff: 1 }), /rule/);
});

test("the summary counts every status and lists the failures", () => {
  const results = [
    { id: "a", status: "identical" },
    { id: "b", status: "within_tolerance" },
    { id: "c", status: "different" },
    { id: "d", status: "error", detail: "boom" },
  ];
  const summary = summarize(results);
  assert.deepEqual(summary.counts, { identical: 1, within_tolerance: 1, different: 1, error: 1 });
  assert.deepEqual(summary.failures.map((r) => r.id), ["c", "d"]);
  assert.equal(summary.total, 4);
});

test("the summary of an empty run is a failure", () => {
  const summary = summarize([]);
  assert.equal(summary.total, 0);
  assert.equal(summary.ok, false);
});

test("the summary is ok only without failures", () => {
  assert.equal(summarize([{ id: "a", status: "identical" }]).ok, true);
  assert.equal(summarize([{ id: "a", status: "different" }]).ok, false);
});

function column(width, height, left, right, split) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      data.set(x < split ? left : right, (y * width + x) * 4);
    }
  }
  return data;
}

test("a difference up to the rounding level is rounding and one more is not", () => {
  const a = image(8, 8, [49, 49, 49, 255]);
  const c = image(8, 8, [49, 49, 49, 255]);
  c[4 * 9] = 49 - ROUNDING_LEVEL - 1;
  assert.equal(explainDifferences(a, c, { width: 8 }).unexplained, 1);
  const b = image(8, 8, [49, 49, 49, 255]);
  b[4 * 9] = 49 - ROUNDING_LEVEL;
  const explained = explainDifferences(a, b, { width: 8 });
  assert.deepEqual([explained.rounding, explained.coverage, explained.unexplained], [1, 0, 0]);
  assert.equal(classify(compareRgba(a, b), explained), "rounding");
});

test("an edge pixel between two colours that the other image shows nearby is coverage", () => {
  const a = column(8, 8, [0, 0, 0, 255], [255, 255, 255, 255], 4);
  const b = column(8, 8, [0, 0, 0, 255], [255, 255, 255, 255], 4);
  b.set([128, 128, 128, 255], (3 * 8 + 3) * 4);
  const explained = explainDifferences(a, b, { width: 8 });
  assert.deepEqual([explained.rounding, explained.coverage, explained.unexplained], [0, 1, 0]);
  assert.equal(classify(compareRgba(a, b), explained), "edge");
});

test("a colour that the other image does not show nearby is unexplained", () => {
  const a = image(8, 8, [10, 10, 10, 255]);
  const b = image(8, 8, [10, 10, 10, 255]);
  b.set([200, 10, 10, 255], (3 * 8 + 3) * 4);
  const explained = explainDifferences(a, b, { width: 8 });
  assert.equal(explained.unexplained, 1);
  assert.deepEqual(explained.box, [3, 3, 3, 3]);
  assert.equal(explained.samples[0].level, 190);
  assert.equal(classify(compareRgba(a, b), explained), "structural");
});

test("an edge moved by two pixels is unexplained even though each pixel sits on an edge", () => {
  const a = column(16, 8, [0, 0, 0, 255], [255, 255, 255, 255], 6);
  const b = column(16, 8, [0, 0, 0, 255], [255, 255, 255, 255], 9);
  const explained = explainDifferences(a, b, { width: 16 });
  assert.ok(explained.unexplained > 0);
});

test("the rows above skipTopRows do not feed the neighbourhood", () => {
  const a = image(4, 4, [10, 10, 10, 255]);
  const b = image(4, 4, [10, 10, 10, 255]);
  b.set([200, 10, 10, 255], (2 * 4 + 1) * 4);
  a.set([200, 10, 10, 255], (1 * 4 + 1) * 4);
  assert.equal(explainDifferences(a, b, { width: 4, skipTopRows: 2 }).unexplained, 1);
  assert.equal(explainDifferences(a, b, { width: 4 }).unexplained, 0);
});

test("the block mean ignores symmetric noise and sees a systematic offset", () => {
  const a = image(32, 32, [100, 100, 100, 255]);
  const noisy = image(32, 32, [100, 100, 100, 255]);
  for (let i = 0; i < 32 * 32; i += 2) {
    noisy[i * 4] = 110;
    noisy[(i + 1) * 4] = 90;
  }
  assert.equal(blockMeanDifference(a, noisy, { width: 32 }), 0);
  const shifted = image(32, 32, [112, 100, 100, 255]);
  assert.equal(blockMeanDifference(a, shifted, { width: 32 }), 12);
});

test("a systematic offset above the block limit makes a rounding or edge difference structural", () => {
  const a = image(32, 32, [100, 100, 100, 255]);
  const b = image(32, 32, [100, 100, 100, 255]);
  assert.ok(MAX_BLOCK_MEAN < 12);
  const explained = { rounding: 0, coverage: 5, unexplained: 0, blockMean: 12 };
  assert.equal(classify(compareRgba(a, b.map((v, i) => (i % 4 === 0 ? 112 : v))), explained), "structural");
});

test("identical images are classified identical", () => {
  const a = image(4, 4, [1, 2, 3, 255]);
  assert.equal(classify(compareRgba(a, a), explainDifferences(a, a, { width: 4 })), "identical");
});
