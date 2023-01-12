from os import listdir
from os.path import isfile, join
import torch
import argparse


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=str)
    args = parser.parse_args()

    for f in listdir(args.path):
        if isfile(join(args.path, f)):
            print(f)
            if '.bin' in f:
                t = torch.load(join(args.path,f), map_location='cpu')
                print(t)
                torch.save(t, join(args.path,f))