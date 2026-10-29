"""Install the small free bilingual streaming wake detector on the Mac."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tarfile
import tempfile
from configure_doubao import save_private
from qwen_speech import config as qwen_config
from wake_detector import configuration

PACKAGE='sherpa-onnx==2.0.1'
MODEL='sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20'
URL='https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/'+MODEL+'.tar.bz2'
SHA256='68447f4fbc67e70eee3a93961f36e81e98f47aef73ce7e7ca00885c6cd3616a6'
FILES=('encoder-epoch-13-avg-2-chunk-16-left-64.int8.onnx','decoder-epoch-13-avg-2-chunk-16-left-64.onnx','joiner-epoch-13-avg-2-chunk-16-left-64.int8.onnx','tokens.txt')
KEYWORDS='HH EY1 M OW1 CH IY0 @HEY_MOTCHI\nHH EY1 M AA1 CH IY0 @HEY_MOTCHI\nn ǐ h ǎo m ò q í @你好莫奇\nh ēi m ò q í @嘿莫奇\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.home()/'Library/Application Support/Mochi/android')
    parser.add_argument('--install',action='store_true')
    parser.add_argument('--archive',type=Path,help='Use an already downloaded official archive, with the same checksum verification.')
    args=parser.parse_args()
    if args.install:
        python,_=qwen_config(args.root)
        subprocess.run([str(python),'-m','pip','install',PACKAGE],check=True)
        with tempfile.TemporaryDirectory(prefix='wake-setup-',dir=args.root) as temp:
            archive=args.archive or Path(temp)/'model.tar.bz2'
            if not args.archive:
                subprocess.run(['curl','--fail','--location','--retry','2','--max-time','240',URL,'--output',str(archive)],check=True)
            if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise ValueError('Wake model checksum does not match the pinned official release.')
            target=args.root/'models/sherpa-kws';target.mkdir(parents=True,exist_ok=True)
            with tarfile.open(archive) as source:
                for name in FILES:
                    member=source.getmember(MODEL+'/'+name)
                    if not member.isfile() or member.size>20000000:raise ValueError('Invalid wake model archive.')
                    (target/name).write_bytes(source.extractfile(member).read())
            (target/'motchi-keywords.txt').write_text(KEYWORDS)
            save_private(args.root/'wake.json',{'python':str(python),'model':str(target),'source':URL,'sha256':SHA256,'runtime':PACKAGE})
    configuration(args.root)
    print('Local bilingual keyword detector configured. Restart Motchi; actual wake accuracy still needs a human test.')

if __name__=='__main__':main()
