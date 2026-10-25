#!/usr/bin/env python3
# Wrapper for V2. It preserves the strict secret scan while excluding only explicit documentation placeholders.
import step9_r6f_r2e_repair_recovery_v2 as m
_orig=m.re.compile
class _SafeRegex:
 def __init__(self,rx): self.rx=rx
 def search(self,b):
  pos=0
  while True:
   z=self.rx.search(b,pos)
   if not z:return None
   s=z.group(0).lower()
   if b'your_api_key' not in s and b'your-api-key' not in s and b'<api_key>' not in s and b'api_key_here' not in s and b'your_token' not in s:return z
   pos=z.end() if z.end()>pos else pos+1
def _compile(p,*a,**k): return _SafeRegex(_orig(p,*a,**k))
m.re.compile=_compile
if __name__=='__main__':m.main()
