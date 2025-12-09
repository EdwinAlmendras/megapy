
function e64 (buffer) {
    return buffer.toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '')
}
  
function d64 (s) {
  return Buffer.from(s, 'base64')
}
export async function generateHashcashToken (challenge) {
    const [versionStr, easinessStr,, tokenStr] = challenge.split(':')
    const version = Number(versionStr)
    if (version !== 1) throw Error('hashcash challenge is not version 1')
  
    const easiness = Number(easinessStr)
    const base = ((easiness & 63) << 1) + 1
    const shifts = (easiness >> 6) * 7 + 3
    const threshold = base << shifts
    const token = d64(tokenStr)
  
    const buffer = Buffer.alloc(4 + 262144 * 48)
    for (let i = 0; i < 262144; i++) {
      buffer.set(token, 4 + i * 48)
    }
  
    while (true) {
      const view = new DataView(await globalThis.crypto.subtle.digest('SHA-256', buffer))
      if (view.getUint32(0) <= threshold) {
        return `1:${tokenStr}:${e64(buffer.slice(0, 4))}`
      }
  
      let j = 0
      while (true) {
        buffer[j]++
        if (buffer[j++]) break
      }
    }
  }

 