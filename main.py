import threading
import subprocess
import time

def run_bank():
    subprocess.run(["python", "bank.py"])

def run_market():
    subprocess.run(["python", "market.py"])

t1 = threading.Thread(target=run_bank)
t2 = threading.Thread(target=run_market)

t1.start()
time.sleep(3)
t2.start()

t1.join()
t2.join()
