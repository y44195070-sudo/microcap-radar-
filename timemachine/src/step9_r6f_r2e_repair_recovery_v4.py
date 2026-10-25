#!/usr/bin/env python3
import re as _re
import step9_r6f_r2e_repair_recovery_v2 as m
class SafeRegex:
 def __init__(self,rx):self.rx=rx
 def search(self,b):
  pos=0
  while True:
   z=self.rx.search(b,pos)
   if not z:return None
   s=z.group(0).lower()
   if not any(q in s for q in (b'your_api_key',b'your-api-key',b'<api_key>',b'api_key_here',b'your_token')):return z
   pos=max(z.end(),pos+1)
class ReProxy:
 def compile(self,p,*a,**k):return SafeRegex(_re.compile(p,*a,**k))
 def __getattr__(self,n):return getattr(_re,n)
m.re=ReProxy()
if __name__=='__main__':m.main()
