import math
import binascii

global_state = {}

# Word size parameters
bs = 28
bx2 = 1 << bs
bm = bx2 - 1
bd = bs >> 1
bdm = (1 << bd) - 1

# Natural log of 2 (if needed)
log2 = math.log(2)

def zeros(n):
    """Return a list of n zeros."""
    return [0] * n


def zclip(r):
    """Trim high-order zero words."""
    n = len(r)
    if n > 0 and r[-1] != 0:
        return r
    while n > 1 and r[n-1] == 0:
        n -= 1
    return r[:n]


def nbits(x):
    """Return bit length of integer x."""
    return x.bit_length() or 1


def badd(a, b):
    """Add multi-precision integers a and b (little-endian limbs)."""
    if len(a) < len(b):
        return badd(b, a)
    r = []
    carry = 0
    for i in range(len(a)):
        ai = a[i]
        bi = b[i] if i < len(b) else 0
        s = ai + bi + carry
        r.append(s & bm)
        carry = s >> bs
    if carry:
        r.append(carry)
    return r


def bsub(a, b):
    """Subtract multi-precision b from a; return [] if negative."""
    if len(b) > len(a):
        return []
    # Check equal-length case
    if len(b) == len(a):
        if b[-1] > a[-1]:
            return []
        if len(b) == 1:
            return [a[0] - b[0]]
    r = []
    carry = 0
    for i in range(len(a)):
        ai = a[i]
        bi = b[i] if i < len(b) else 0
        diff = ai - bi + carry
        r.append(diff & bm)
        carry = diff >> bs
    if carry:
        return []
    return zclip(r)


def ip(w, n, x, y, c):
    """Internal product for multiply and square operations."""
    xl = x & bdm
    xh = x >> bd
    yl = y & bdm
    yh = y >> bd
    m = xh * yl + yh * xl
    l = xl * yl + ((m & bdm) << bd) + w[n] + c
    w[n] = l & bm
    c = xh * yh + (m >> bd) + (l >> bs)
    return c


def bsqr(x):
    """Multiple-precision squaring (HAC 14.16)."""
    t = len(x)
    r = zeros(2 * t)
    for i in range(t):
        c = ip(r, 2*i, x[i], x[i], 0)
        for j in range(i+1, t):
            c = ip(r, i+j, 2*x[j], x[i], c)
        r[i+t] = c
    return zclip(r)


def bmul(x, y):
    """Multiple-precision multiplication (HAC 14.12)."""
    n, t = len(x), len(y)
    r = zeros(n + t)
    for i in range(t):
        c = 0
        for j in range(n):
            c = ip(r, i+j, x[j], y[i], c)
        r[i+n] = c
    return zclip(r)


def toppart(x, start, length):
    """Return top bits of x starting at limb `start` over `length` limbs."""
    v = 0
    for i in range(length):
        if start - i < 0:
            break
        v = (v << bs) + x[start - i]
    return v


def bdiv(a, b):
    """Multiple-precision division (HAC 14.20): returns global_state with 'q' and 'mod'."""
    n, t = len(a)-1, len(b)-1
    nmt = n - t
    # a < b
    if n < t or (n == t and (a[n] < b[n] or (n>0 and a[n]==b[n] and a[n-1]<b[n-1]))):
        global_state['q'] = [0]
        global_state['mod'] = a.copy()
        return global_state
    # small quotient
    if n == t and toppart(a, t, 2) / toppart(b, t, 2) < 4:
        x = a.copy()
        qq = 0
        while True:
            xx = bsub(x, b)
            if not xx:
                break
            x = xx
            qq += 1
        global_state['q'] = [qq]
        global_state['mod'] = x
        return global_state
    # normalize
    shift2 = b[t].bit_length()
    shift = bs - shift2
    x = a.copy()
    y = b.copy()
    if shift:
        for i in range(t, 0, -1):
            y[i] = ((y[i] << shift) & bm) | (y[i-1] >> shift2)
        y[0] = (y[0] << shift) & bm
        if x[n] & ((bm << shift2) & bm):
            x.append(0)
            nmt += 1
        for i in range(n, 0, -1):
            x[i] = ((x[i] << shift) & bm) | (x[i-1] >> shift2)
        x[0] = (x[0] << shift) & bm
    # main loop
    q = zeros(nmt+1)
    y2 = zeros(nmt) + y
    # initial subtractive
    while True:
        x2 = bsub(x, y2)
        if not x2:
            break
        q[nmt] += 1
        x = x2
    yt = y[t]
    top = toppart(y, t, 2)
    for i in range(n, t, -1):
        m_idx = i - t - 1
        if i >= len(x):
            qm = 1
        elif x[i] == yt:
            qm = bm
        else:
            qm = toppart(x, i, 2) // yt
        while qm * top > toppart(x, i, 3):
            qm -= 1
        y2 = y2[1:]
        x2 = bsub(x, bmul([qm], y2))
        if not x2:
            qm -= 1
            x2 = bsub(x, bmul([qm], y2))
        x = x2
        q[m_idx] = qm
    # de-normalize
    if shift:
        for i in range(len(x)-1):
            x[i] = (x[i] >> shift) | ((x[i+1] << shift2) & bm)
        x[-1] >>= shift
    global_state['q'] = zclip(q)
    global_state['mod'] = zclip(x)
    return global_state


def simplemod(i, m):
    """Return i mod m for small m < 2^bd."""
    c = 0
    for v in reversed(i):
        c = ((v >> bd) + (c << bd)) % m
        c = ((v & bdm) + (c << bd)) % m
    return c


def bmod(p, m):
    """General multi-precision modulus."""
    if len(m) == 1:
        if len(p) == 1:
            return [p[0] % m[0]]
        if m[0] < bdm:
            return [simplemod(p, m[0])]
    res = bdiv(p, m)
    return res['mod']


def bmod2(x, m, mu):
    """Barrett reduction (HAC 14.42)."""
    ml = len(m)
    if len(x) > (ml << 1):
        return bmod2(x[:-2*ml] + bmod2(x[-2*ml:], m, mu), m, mu)
    ml1 = ml + 1
    q3 = bmul(x[ml-1:], mu)[ml1:]
    r1 = x[:ml1]
    r2 = bmul(q3, m)[:ml1]
    r = bsub(r1, r2)
    if not r:
        r1 = r1 + [1]
        r = bsub(r1, r2)
    while True:
        rr = bsub(r, m)
        if not rr:
            break
        r = rr
    return r


def bmodexp(g, e, m):
    """Modular exponentiation using Barrett reduction."""
    a = g.copy()
    l = len(e) - 1
    n = len(m) * 2
    mu = zeros(n+1)
    mu[n] = 1
    mu = bdiv(mu, m)['q']
    bit = e[l].bit_length() - 1
    for i in range(l, -1, -1):
        for j in range(bit, -1, -1):
            a = bmod2(bsqr(a), m, mu)
            if (e[i] >> j) & 1:
                a = bmod2(bmul(a, g), m, mu)
        bit = bs - 1
    return a


def RSAdecrypt(m, d, p, q, u):
    """Compute m^d mod p*q via CRT."""
    xp = bmodexp(bmod(m, p), bsub(d, [1]), p)
    xq = bmodexp(bmod(m, q), bsub(d, [1]), q)
    t = bsub(xq, xp)
    if not t:
        t = bsub(xp, xq)
        t = bmod(bmul(t, u), q)
        t = bsub(q, t)
    else:
        t = bmod(bmul(t, u), q)
    return badd(bmul(t, p), xp)




# mpi2big int
def mpi2b(data: bytes):
    if len(data) < 2:
        return []

    b0, b1 = data[0], data[1]
    bits = (b0 << 8) + b1
    
    expected_min = (len(data)-2)*8 - 8
    expected_max = (len(data)-2)*8
    
    if bits < expected_min or bits > expected_max:
        return []
    r = [0]
    rn = 0
    bn = 1
    sb = 256  # shadow bit used for shifting byte-wise
    sn = len(data)

    # Validate bit size vs data size
    expected_min = (sn - 2) * 8 - 8
    expected_max = (sn - 2) * 8
    if bits > expected_max or bits < expected_min:
        return []

    byte_index = sn - 1
    c = data[byte_index]

    for n in range(bits):

        if (sb << 1) > 255:
            sn -= 1
            sb = 1
            if sn < 2:
                break
            c = data[sn]
        else:
            sb <<= 1

        if bn > bm:
            bn = 1
            r.append(0)
            rn += 1

        if c & sb:
            r[rn] |= bn
        
        bn <<= 1

    return r

def b2s(b: list):
    """Convert limbs to binary string (returned as bytes)."""
    bits = len(b) * bs
    r = []
    bn = 1
    bc = 0
    rb = 1
    rn = 0
    out = []
    for n in range(bits):
        if b[bc] & bn:
            if len(out) <= rn:
                out.append(0)
            out[rn] |= rb
        rb <<= 1
        if rb > 255:
            rb = 1
            rn += 1
        bn <<= 1
        if bn > bm:
            bn = 1
            bc += 1
    # strip leading zeros
    while out and out[-1] == 0:
        out.pop()
    return bytes(out)


def crypto_decode_priv_key(privk: bytes):
    """Decode an RSA private key in MPI format."""
    pubkey = []
    data = privk
    for i in range(4):
        if len(data) < 2:
            return None
        bits = (data[0] << 8) + data[1]
        l = (bits + 7) // 8 + 2
        limb = mpi2b(data[:l])
        if not limb:
            return None
        pubkey.append(limb)
        data = data[l:]
    return pubkey


def crypto_rsa_decrypt(ciphertext: bytes, privkey):
    """Decrypt ciphertext with RSA private key (MPI-based)."""
    ci = mpi2b(ciphertext)
    pt_limbs = RSAdecrypt(ci, privkey[2], privkey[0], privkey[1], privkey[3])
    return b2s(pt_limbs)


def mpi_to_int(s: bytes) -> int:
    """Converts MPI format to integer."""
    return int(binascii.hexlify(s[2:]), 16)
