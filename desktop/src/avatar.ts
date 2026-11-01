const invalid = "PNG, JPG, WebP 사진을 선택하세요.";

export function imageType(header: Uint8Array): string {
  if (
    [137, 80, 78, 71, 13, 10, 26, 10].every(
      (byte, index) => header[index] === byte,
    )
  )
    return "image/png";
  if (header[0] === 255 && header[1] === 216 && header[2] === 255)
    return "image/jpeg";
  if (
    header.length >= 12 &&
    String.fromCharCode(...header.slice(0, 4)) === "RIFF" &&
    String.fromCharCode(...header.slice(8, 12)) === "WEBP"
  )
    return "image/webp";
  throw Error(invalid);
}

export async function readAvatar(file: File): Promise<string> {
  if (!file.size || file.size > 5 * 1024 * 1024)
    throw Error("5MB 이하의 사진을 선택하세요.");
  const type = imageType(new Uint8Array(await file.slice(0, 12).arrayBuffer()));
  const url = URL.createObjectURL(file.slice(0, file.size, type));
  const image = new Image();
  try {
    image.src = url;
    try {
      await image.decode();
    } catch {
      throw Error("사진을 읽지 못했습니다. 다른 파일을 선택하세요.");
    }
    if (
      !image.naturalWidth ||
      !image.naturalHeight ||
      image.naturalWidth * image.naturalHeight > 25000000
    )
      throw Error("사진 크기가 너무 큽니다.");
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 256;
    const context = canvas.getContext("2d");
    if (!context) throw Error("사진을 불러오지 못했습니다.");
    const side = Math.min(image.naturalWidth, image.naturalHeight);
    context.drawImage(
      image,
      (image.naturalWidth - side) / 2,
      (image.naturalHeight - side) / 2,
      side,
      side,
      0,
      0,
      256,
      256,
    );
    const result = canvas.toDataURL("image/png");
    if (!result.startsWith("data:image/png;base64,"))
      throw Error("사진을 변환하지 못했습니다.");
    return result;
  } finally {
    image.src = "";
    URL.revokeObjectURL(url);
  }
}
