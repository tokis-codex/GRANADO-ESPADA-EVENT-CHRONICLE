"""Fetch the official GE favicon and convert it to a Windows .ico file.
Never synthesize or substitute an unrelated icon.
"""
import io, re, sys
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from PIL import Image

HOME='https://ge.hanbiton.com/Home/Home.aspx'
OUT=Path(__file__).parent/'ge.ico'

def main():
    s=requests.Session();s.headers['User-Agent']='Mozilla/5.0'
    response=s.get(HOME,timeout=20);response.raise_for_status()
    soup=BeautifulSoup(response.content,'html.parser')
    urls=[]
    for link in soup.find_all('link',href=True):
        rel=' '.join(link.get('rel',[])).lower()
        if 'icon' in rel:urls.append(urljoin(response.url,link['href']))
    # Conventional favicon endpoint checked only if the site doesn't specify a link.
    urls.append('https://ge.hanbiton.com/favicon.ico')
    errors=[]
    for url in dict.fromkeys(urls):
        try:
            r=s.get(url,timeout=20);r.raise_for_status()
            if len(r.content)>3_000_000:raise ValueError('oversized file')
            im=Image.open(io.BytesIO(r.content));im.load()
            if im.width<16 or im.height<16:raise ValueError('icon is too small')
            im.convert('RGBA').save(OUT,format='ICO',sizes=[(x,x) for x in (16,24,32,48,64,128,256) if x<=max(im.size)])
            if OUT.stat().st_size<100:raise ValueError('empty ICO')
            print('Official GE favicon saved:',url,OUT)
            return 0
        except Exception as e:errors.append(f'{url}: {e}')
    print('ERROR: Could not acquire the official GE favicon. Do not use a substitute icon.')
    for e in errors:print(e)
    return 1

if __name__=='__main__':sys.exit(main())
