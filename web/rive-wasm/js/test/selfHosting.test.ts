import fs from "fs";
import path from "path";
import { Rive, RiveFile, RuntimeLoader } from "../src/rive";

const hostedImageFile = (): ArrayBuffer => {
  const bytes = fs.readFileSync(
    path.join(
      __dirname,
      "../../../../runtime/tests/unit_tests/assets/hosted_image_file.riv",
    ),
  );
  return bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  ) as ArrayBuffer;
};

const isExternal = (url: string | null): boolean =>
  url !== null && /^(https?:)?\/\//.test(url);

describe("self hosting", () => {
  let opened: string[];

  beforeEach(() => {
    opened = [];
    jest
      .spyOn(XMLHttpRequest.prototype, "open")
      .mockImplementation(function (_method: string, url: string | URL) {
        opened.push(String(url));
      });
    jest.spyOn(XMLHttpRequest.prototype, "send").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test("the default wasm URLs point to no third-party host", () => {
    expect(isExternal(RuntimeLoader.getWasmUrl())).toBe(false);
    expect(isExternal(RuntimeLoader.getWasmFallbackUrl())).toBe(false);
  });

  describe("the default wasm URLs beside the loading script", () => {
    const withScript = (src: string | undefined): [string, string | null] => {
      Object.defineProperty(document, "currentScript", {
        configurable: true,
        get: () => (src === undefined ? null : { src }),
      });
      let urls: [string, string | null] = ["", null];
      jest.isolateModules(() => {
        const { RuntimeLoader: Fresh } = require("../src/runtimeLoader");
        urls = [Fresh.getWasmUrl(), Fresh.getWasmFallbackUrl()];
      });
      return urls;
    };

    afterEach(() => {
      delete (document as any).currentScript;
    });

    test("resolve next to the script", () => {
      expect(withScript("https://example.test/dist/rive.js")).toEqual([
        "https://example.test/dist/rive.wasm",
        "https://example.test/dist/rive_fallback.wasm",
      ]);
    });

    test("keep the bare names without a classic script", () => {
      expect(withScript(undefined)).toEqual(["rive.wasm", "rive_fallback.wasm"]);
    });

    test("keep the bare names when the script URL has no base", () => {
      expect(withScript("blob:null/3f1a")).toEqual([
        "rive.wasm",
        "rive_fallback.wasm",
      ]);
    });
  });

  test("a RiveFile does not request the Rive asset CDN by default", async () => {
    const file = new RiveFile({ buffer: hostedImageFile() });
    await file.init();
    expect(opened.filter(isExternal)).toEqual([]);
    file.cleanup();
  });

  test("a Rive instance does not request the Rive asset CDN by default", (done) => {
    const canvas = document.createElement("canvas");
    const r = new Rive({
      canvas,
      buffer: hostedImageFile(),
      autoplay: false,
      onLoad: () => {
        expect(opened.filter(isExternal)).toEqual([]);
        r.cleanup();
        done();
      },
    });
  });

  test("the CDN is still available when asked for", async () => {
    const file = new RiveFile({
      buffer: hostedImageFile(),
      enableRiveAssetCDN: true,
    });
    await file.init();
    expect(opened.filter(isExternal).length).toBeGreaterThan(0);
    file.cleanup();
  });
});
