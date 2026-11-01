import { expect, test } from "vitest";
import { imageType, readAvatar } from "./avatar";

test.each([
  [[137, 80, 78, 71, 13, 10, 26, 10], "image/png"],
  [[255, 216, 255, 224], "image/jpeg"],
  [[82, 73, 70, 70, 16, 0, 0, 0, 87, 69, 66, 80], "image/webp"],
])("확장자나 MIME 정보 없이 이미지 형식을 판별한다", (bytes, type) => {
  expect(imageType(new Uint8Array(bytes as number[]))).toBe(type);
});
test.each([
  [],
  [137, 80, 78],
  [255, 216],
  [60, 115, 118, 103],
  [82, 73, 70, 70, 0, 0, 0, 0, 65, 86, 73, 32],
])("빈 파일과 다른 형식은 거부한다", (...bytes) => {
  expect(() => imageType(new Uint8Array(bytes as number[]))).toThrow(
    "PNG, JPG, WebP",
  );
});
test("크기 제한을 넘는 파일은 읽거나 디코딩하지 않는다", async () => {
  await expect(
    readAvatar({ size: 5 * 1024 * 1024 + 1 } as File),
  ).rejects.toThrow("5MB");
});
