# /opt/msmacro-app/msmacro/webapp.py
import sys
print("[msmacro] webapp.py is deprecated. Use: python -m msmacro.web.server", file=sys.stderr)
from .web.server import main
if __name__ == "__main__":
    main()
