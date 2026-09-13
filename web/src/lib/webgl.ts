/**
 * deck.gl and MapLibre both need a WebGL context. Without one they fail deep
 * inside their own init and leave an unpainted canvas, so the page looks broken
 * with no explanation. Checking up front lets the app say what went wrong and
 * keep the parts that still work.
 */
export function hasWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas');
    const gl =
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl');
    if (!gl) return false;
    // A context can exist but be immediately lost on a blocklisted driver.
    return !(gl as WebGLRenderingContext).isContextLost?.();
  } catch {
    return false;
  }
}
