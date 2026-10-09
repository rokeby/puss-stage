import os

script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p94_s3_arrival.py")
exec(compile(open(script, encoding="utf-8").read(), script, "exec"), {"__name__": "__main__"})
