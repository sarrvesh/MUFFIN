#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 12 12:51:56 2020

@author: thecuriosvambo
"""

import argparse
from deconv3d import EasyMuffin, EasyMuffinSURE 
from astropy.io import fits
from deconv3d_tools import conv, fix_dim
import numpy as np
import matplotlib.pyplot as plt 



parser=argparse.ArgumentParser()
parser.add_argument('-d','--dirty',help='add path to dirty image fits file')
parser.add_argument('-p','--psf',help='add path to psf fits file')
parser.add_argument('-N','--niter',help='add number of iterations', type=int)
parser.add_argument('-s','--save',help='save output', type=int)
parser.add_argument('-C','--channels',help='number of channels', type=int)
args = parser.parse_args()

dirtyim=args.dirty
psfim=args.psf
niter=args.niter
Save=args.save
L=args.channels


psffits=fix_dim(fits.getdata(psfim, ext=0))[:,:,0:L]
dirtyfits=fix_dim(fits.getdata(dirtyim, ext=0))[:,:,0:L]


b= EasyMuffinSURE(psf=psffits,dirty=dirtyfits,save=Save)
b.loop(niter)

#u=np.load('u.npy',allow_pickle=True)
#v=np.load('v.npy', allow_pickle=True)
#x0=np.load('x0_tst.npy', allow_pickle=True)
x1=b.x

x0=np.transpose(x1)

#print(x0)

hdu=fits.PrimaryHDU(data=x0)
hdu.writeto('/home/thecuriosvambo/Work/MUFFIN/muffin/muff_sure_content/muff_sure_x0.fits', overwrite=True)


#testfits=fits.open('x0.fits')
#print(testfits[0].data)

for i in range(L):
    filename = '/home/thecuriosvambo/Work/MUFFIN/muffin/muff_sure_content/chan_{:03d}.png'.format(i)
    #print(filename)
    plt.imshow(x1[:,:,i])
    plt.savefig(filename)
    plt.close()
    #plt.show()
