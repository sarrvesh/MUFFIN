from astropy.io import fits
from sklearn.metrics import mean_squared_error
import argparse
import numpy as np


parser=argparse.ArgumentParser()
parser.add_argument('-M','--Muff',help='add path to muffin Fits file image')
parser.add_argument('-MS','--MuffSure',help='add path to muffin sure fits file image')
parser.add_argument('-C','--channels',help='number of channels', type=int)
args = parser.parse_args()

L=args.channels
Muff_file=args.Muff
MuffSure_file=args.MuffSure



Muff_Image = fits.open(Muff_file)
Muff_Sure_Image=fits.open(MuffSure_file)



Muff_data= Muff_Image[0].data
Muff_Sure_data=Muff_Sure_Image[0].data

for i in range(L):
    Muff_stdd = np.std(Muff_data[:,:,i])
    Muff_Sure_stdd=np.std(Muff_Sure_data[:,:,i])
    print("Chan0%i: Muff_stdd: %f, Muff_sure_stdd: %f" %(i+1,Muff_stdd,Muff_Sure_stdd))

