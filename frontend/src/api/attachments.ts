import { postFile } from './client'

export const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
export const MAX_IMAGE_MB = 10

export function imageProblem(file: File): string | null {
  if (!IMAGE_TYPES.includes(file.type)) {
    return `${file.name} cannot be attached: only PNG, JPEG, GIF and WebP images are supported.`
  }
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
    return `${file.name} cannot be attached: images can be at most ${String(MAX_IMAGE_MB)} MB.`
  }
  return null
}

export async function uploadImage(file: File): Promise<string> {
  return (await postFile<{ url: string }>('/attachments', file)).url
}
