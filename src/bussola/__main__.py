import sys

from bussola.handler.opening import COMMAND

if __name__ == "__main__":
    if sys.argv[1:2] == [COMMAND]:
        from bussola.handler.opening import main
    else:
        from bussola.cli import main
    main()
