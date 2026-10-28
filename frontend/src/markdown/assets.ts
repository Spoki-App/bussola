const GITHUB_ASSET = /^https:\/\/github\.com\/(?:user-attachments\/assets\/[0-9a-f-]{36}|[\w.-]+\/[\w.-]+\/assets\/\d+\/[0-9a-f-]{36})$/

export function imageSource(src: string): string {
  return GITHUB_ASSET.test(src) ? `/api/forge/asset?url=${encodeURIComponent(src)}` : src
}
