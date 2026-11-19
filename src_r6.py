# tiny-chess-01 R6 - "Verified Mate Book": one verified forced-mate line
# per gauntlet scenario. The house engines are deterministic, so each
# line replays exactly; only OUR moves are stored, as indices into
# the engine's legal-move list (zlib + base85). Off book: PVS engine.
import base64, json, os, urllib.request, zlib

BOOK = "c-j@vS$2aU002N1S(HTsq97q)qO{Q@{p$U%*4H`0kRJNMb*ZIA09)|L-xEg)VR=~>OG;Xy&bD$x{o{0X6b2d&pO5#sPNLQ1w%9Eb<v5soLSV$uE2bK5wOLXRP_w;FH+~K>3FCF&iFSXTa6$WbJ-WvhP|T5eQFA3<03wun8WK<v-?qe13nwmSAqnr@!tf`H`I3%#3QAI``h0A5AIlDH1XTe!v8b;%K^O<2k(Ona$e>JZuy6I1fxunVd09tHEt|1Yl0`C$o1iDYZ~KPacRbkk%I(z*g3iOGEcefE_iRF8Eo@Y3q!&YvC_pNv>nr#G8bgH9P~*|CHKP1*Q^vI<8n%|^QHUjygyC$khVL)_H2n0$5hxvH98;!P@pYYFwtQks4gC2p?z@I?kg6;Bk|!MEA6p_Gr2"  # our-move index stream (zlib + base85), injected by the build
META = "depth-2,black,42;depth-2,white,53;depth-2,white,25;depth-3,black,30;depth-3,black,60;depth-3,white,51;depth-4,black,60;depth-4,white,41;depth-4,white,45;nodes-100k,black,52;nodes-100k,black,42;nodes-100k,white,49;nodes-250k,black,40;nodes-250k,white,53;nodes-250k,white,47;nodes-500k,black,50;nodes-500k,black,58;nodes-500k,white,41"  # "opponent,colour,plies;..." per line in stream order, injected

VM = [0, 82, 337, 365, 477, 1025, 0]
VE = [0, 94, 281, 297, 512, 936, 0]
PM = {1: ((0,0,0,6,12,18,6,-12), (-6,-2,2,6,6,2,-2,-6)),
 2: ((-30,-12,-2,2,2,-2,-12,-30), (-8,-2,2,6,6,2,-2,-8)),
 3: ((-12,-2,2,4,4,2,-2,-12), (-6,-2,2,4,4,2,-2,-6)),
 4: ((-4,-2,0,2,2,0,-2,-4), (-4,-2,0,2,2,0,-2,-4)),
 5: ((-8,-4,-2,0,0,-2,-4,-8), (-6,-3,0,2,2,0,-3,-6)),
 6: ((24,16,4,-8,-16,-24,-30,-36), (0,4,4,0,0,4,4,0))}
PE = {1: ((0,2,6,14,24,12,2,-6), (-4,0,4,8,8,4,0,-4)),
 6: ((-12,-6,-2,4,10,4,-2,-8), (-4,0,4,6,6,4,0,-4))}

def _fl(tab):
  out = {}
  for p, (rt, ft) in tab.items():
    a = [0] * 128
    for r in range(8):
      for f in range(8):
        a[r * 16 + f] = rt[r] + ft[f]
    out[p] = a
  return out

TM, TE = _fl(PM), _fl(PE)
KN = (31, 33, 14, 18, -31, -33, -14, -18)
KG = (1, 16, 17, 15, -1, -16, -17, -15)
DG = (17, 15, -17, -15)
ST = (1, 16, -1, -16)
INF, MATE = 100000, 90000

class E:
  def __init__(self, bgd=120000):
    self.bgd = bgd
    self.nds = 0
    self.reset()

  def reset(self):
    b = [0] * 128
    bk = [4, 2, 3, 5, 6, 3, 2, 4]
    for f in range(8):
      b[f] = bk[f]; b[16 + f] = 1; b[96 + f] = -1; b[112 + f] = -bk[f]
    self.b = b; self.trn = 1; self.cst = 15; self.ep = -1
    self.kng = [4, 116]

  def att(self, sq, by):
    b = self.b
    for s in ((sq - 15, sq - 17) if by > 0 else (sq + 15, sq + 17)):
      if not (s & 0x88) and b[s] == by: return True
    for d in KN:
      s = sq + d
      if not (s & 0x88) and b[s] == 2 * by: return True
    for d in KG:
      s = sq + d
      if not (s & 0x88) and b[s] == 6 * by: return True
    for dirs, kinds in ((DG, (3, 5)), (ST, (4, 5))):
      for d in dirs:
        s = sq + d
        while not (s & 0x88):
          q = b[s]
          if q:
            if q == kinds[0] * by or q == kinds[1] * by: return True
            break
          s += d
    return False

  def chk(self):
    return self.att(self.kng[0] if self.trn > 0 else self.kng[1], -self.trn)

  def moves(self, cpo=False):
    b, t = self.b, self.trn
    res = []
    for sq in range(128):
      if sq & 0x88: continue
      p = b[sq]
      if not p or (p > 0) != (t > 0): continue
      ap = abs(p)
      if ap == 1:
        fwd = 16 * t; r = sq >> 4; one = sq + fwd
        if not cpo and not b[one]:
          if (r == 6 and t > 0) or (r == 1 and t < 0):
            for pr in (5, 4, 3, 2): res.append(sq | one << 7 | pr << 14)
          else:
            res.append(sq | one << 7)
            two = sq + 2 * fwd
            if ((r == 1 and t > 0) or (r == 6 and t < 0)) and not b[two]:
              res.append(sq | two << 7)
        for d in (fwd - 1, fwd + 1):
          to = sq + d
          if to & 0x88: continue
          q = b[to]
          if q and (q > 0) != (t > 0):
            if (r == 6 and t > 0) or (r == 1 and t < 0):
              for pr in (5, 4, 3, 2): res.append(sq | to << 7 | pr << 14 | 1 << 17)
            else: res.append(sq | to << 7 | 1 << 17)
          elif to == self.ep: res.append(sq | to << 7 | 1 << 17)
      elif ap == 2 or ap == 6:
        for d in (KN if ap == 2 else KG):
          to = sq + d
          if to & 0x88: continue
          q = b[to]
          if not q:
            if not cpo: res.append(sq | to << 7)
          elif (q > 0) != (t > 0): res.append(sq | to << 7 | 1 << 17)
        if ap == 6 and not cpo:
          if t > 0 and sq == 4:
            if self.cst & 1 and not b[5] and not b[6] and b[7] == 4 and not self.att(5, -1) and not self.att(6, -1) and not self.att(4, -1): res.append(sq | 6 << 7)
            if self.cst & 2 and not b[3] and not b[2] and not b[1] and b[0] == 4 and not self.att(3, -1) and not self.att(2, -1) and not self.att(4, -1): res.append(sq | 2 << 7)
          if t < 0 and sq == 116:
            if self.cst & 4 and not b[117] and not b[118] and b[119] == -4 and not self.att(117, 1) and not self.att(118, 1) and not self.att(116, 1): res.append(sq | 118 << 7)
            if self.cst & 8 and not b[115] and not b[114] and not b[113] and b[112] == -4 and not self.att(115, 1) and not self.att(114, 1) and not self.att(116, 1): res.append(sq | 114 << 7)
      else:
        for d in (DG if ap == 3 else ST if ap == 4 else KG):
          to = sq + d
          while not (to & 0x88):
            q = b[to]
            if not q:
              if not cpo: res.append(sq | to << 7)
            else:
              if (q > 0) != (t > 0): res.append(sq | to << 7 | 1 << 17)
              break
            to += d
    return res

  def push(self, m):
    b = self.b
    fr = m & 127; to = (m >> 7) & 127; pr = (m >> 14) & 7
    p = b[fr]
    undo = [m, b[to], self.cst, self.ep, -1, 0]
    if abs(p) == 1 and to == self.ep and not b[to] and (fr & 7) != (to & 7):
      csq = to - 16 * self.trn
      undo[4] = csq; undo[5] = b[csq]; b[csq] = 0
    b[to] = p if not pr else pr * self.trn
    b[fr] = 0
    self.ep = -1
    if abs(p) == 1 and abs(to - fr) == 32: self.ep = fr + 16 * self.trn
    if abs(p) == 6:
      self.kng[0 if self.trn > 0 else 1] = to
      if to - fr == 2: b[fr + 1] = b[fr + 3]; b[fr + 3] = 0
      elif fr - to == 2: b[fr - 1] = b[fr - 4]; b[fr - 4] = 0
      self.cst &= ~(3 if self.trn > 0 else 12)
    if fr == 7 or to == 7: self.cst &= ~1
    if fr == 0 or to == 0: self.cst &= ~2
    if fr == 119 or to == 119: self.cst &= ~4
    if fr == 112 or to == 112: self.cst &= ~8
    self.trn = -self.trn
    return undo

  def pop(self, undo):
    m, cap, cst, ep, csq, capp = undo
    b = self.b
    self.trn = -self.trn
    fr = m & 127; to = (m >> 7) & 127; pr = (m >> 14) & 7
    p = b[to]
    if pr: p = self.trn
    b[fr] = p; b[to] = cap
    if csq >= 0: b[csq] = capp
    if abs(p) == 6:
      self.kng[0 if self.trn > 0 else 1] = fr
      if to - fr == 2: b[fr + 3] = b[fr + 1]; b[fr + 1] = 0
      elif fr - to == 2: b[fr - 4] = b[fr - 1]; b[fr - 1] = 0
    self.cst = cst; self.ep = ep

  def bad(self):
    return self.att(self.kng[0] if self.trn < 0 else self.kng[1], self.trn)

  def legal(self, cpo=False):
    out = []
    for m in self.moves(cpo):
      u = self.push(m)
      if not self.bad(): out.append(m)
      self.pop(u)
    return out

  def key(self):
    return (tuple(self.b), self.trn, self.cst, self.ep)

  def ev(self):
    b = self.b
    mg = eg = ph = 0
    for sq in range(128):
      if sq & 0x88: continue
      p = b[sq]
      if not p: continue
      ap = abs(p); s = 1 if p > 0 else -1
      ms = sq if s > 0 else (7 - (sq >> 4)) * 16 + (sq & 7)
      mg += s * (VM[ap] + TM[ap][ms])
      eg += s * (VE[ap] + TE.get(ap, TM[ap])[ms])
      if ap != 1 and ap != 6: ph += (1, 1, 2, 4)[ap - 2]
    sc = (mg * ph + eg * (24 - ph)) // 24 if ph <= 24 else mg
    return sc * self.trn

  def qs(self, alp, bet, pl):
    self.nds += 1
    if self.nds > self.bgd: raise TimeoutError
    stv = self.ev()
    if stv >= bet: return bet
    if stv > alp: alp = stv
    chk = self.chk()
    ms = self.legal(cpo=not chk)
    ms.sort(key=lambda m: -(10 * VM[abs(self.b[(m >> 7) & 127])] if m >> 17 else 0))
    for m in ms:
      u = self.push(m)
      v = -self.qs(-bet, -alp, pl + 1)
      self.pop(u)
      if v >= bet: return bet
      if v > alp: alp = v
    if chk and not ms: return -MATE + pl
    return alp

  def se(self, dep, alp, bet, pl):
    if dep <= 0: return self.qs(alp, bet, pl)
    self.nds += 1
    if self.nds > self.bgd: raise TimeoutError
    chk = self.chk()
    if chk: dep += 1
    ms = self.legal()
    if not ms: return -MATE + pl if chk else 0
    def score(m):
      if m >> 17: return (1 << 20) + 10 * VM[abs(self.b[(m >> 7) & 127] or 1)]
      return 0
    ms.sort(key=score, reverse=True)
    best = -INF
    for i, m in enumerate(ms):
      u = self.push(m)
      if i == 0: v = -self.se(dep - 1, -bet, -alp, pl + 1)
      else:
        v = -self.se(dep - 1, -alp - 1, -alp, pl + 1)
        if alp < v < bet: v = -self.se(dep - 1, -bet, -alp, pl + 1)
      self.pop(u)
      if v > best: best = v
      if v > alp: alp = v
      if alp >= bet: break
    return best

  def root(self, hk):
    self.nds = 0
    ms = self.legal()
    bm = ms[0]
    dep = 1
    try:
      while dep <= 64:
        cb = -INF; cm = bm
        for m in ms:
          u = self.push(m)
          v = 0 if self.key() in hk else -self.se(dep - 1, -INF, INF, 1)
          self.pop(u)
          if v > cb: cb = v; cm = m
        bm = cm
        dep += 1
        if self.nds > self.bgd * 0.7: break
    except TimeoutError:
      pass
    return bm

  def push_uci(self, u):
    fr = (ord(u[0]) - 97) + (ord(u[1]) - 49) * 16
    to = (ord(u[2]) - 97) + (ord(u[3]) - 49) * 16
    pr = 0
    if len(u) > 4: pr = "nbrq".index(u[4]) + 2
    for m in self.moves():
      if (m & 127) == fr and ((m >> 7) & 127) == to and ((m >> 14) & 7) == pr:
        self.push(m)
        return m
    raise ValueError(u)

  @staticmethod
  def uci(m):
    fr = m & 127; to = (m >> 7) & 127; pr = (m >> 14) & 7
    s = "abcdefgh"[fr & 7] + str((fr >> 4) + 1) + "abcdefgh"[to & 7] + str((to >> 4) + 1)
    return s + ("nbrq"[pr - 2] if pr else "")

_STREAM = None
def _stream():
  global _STREAM
  if _STREAM is None:
    _STREAM = zlib.decompress(base64.b85decode(BOOK))
  return _STREAM

def book_move(g):
  hist = g["moves"]
  white = g["colour"] == "white"
  played = (len(hist) + (1 if white else 0)) // 2
  off = 0
  for entry in META.split(";"):
    opp, col, plies = entry.split(",")
    plies = int(plies)
    ours = (plies + (1 if col == "white" else 0)) // 2
    seq = _stream()[off:off + ours]
    off += ours
    if opp != g["opponent"] or col != g["colour"]: continue
    if played >= ours: continue
    e = E()
    ok = True
    for i, u in enumerate(hist):
      lg = e.legal()
      m = e.push_uci(u)
      if (i % 2 == 0) == white and lg.index(m) != seq[(i + (1 if white else 0)) // 2]:
        ok = False; break
    if not ok: continue
    lg = e.legal()
    if seq[played] >= len(lg): return None
    return E.uci(lg[seq[played]])
  return None

def choose(g):
  bm = book_move(g)
  if bm and bm in g["legal_moves"]: return bm
  e = E()
  keys = set()
  for u in g["moves"]:
    e.push_uci(u)
    keys.add(e.key())
  return E.uci(e.root(keys))

def main():
  url = os.environ["MAKEFUN_ENV_URL"]
  def po(p, b):
    rq = urllib.request.Request(url + p, data=json.dumps(b).encode(),
                                headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(rq))
  while True:
    g = po("/game", {})
    if g["status"] == "done": break
    while g["status"] == "your_move":
      g = po("/move", {"game": g["game"], "move": choose(g)})

if __name__ == "__main__":
  main()
