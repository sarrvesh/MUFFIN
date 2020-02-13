#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 12 12:51:56 2020

@author: thecuriosvambo
"""

import argparse
from deconv3d import EasyMuffin
from astropy.io import fits
from deconv3d_tools import conv, fix_dim

parser=argparse.ArgumentParser()
parser.add_argument('-d','--dirty',help='add path to dirty image fits file')
parser.add_argument('-p','--psf',help='add path to psf fits file')
parser.add_argument('-N','--niter',help='add number of iterations', type=int)
args = parser.parse_args()

dirtyim=args.dirty
psfim=args.psf
niter=args.niter

#dirtyfits=fits.open(dirtyim)
#psffits=fits.open(psfim)

L=5

#dirtyfits=dirtyfits[0].data
#psffits=psffits[0].data

psffits=fix_dim(fits.getdata(psfim, ext=0))[:,:,0:L]
dirtyfits=fix_dim(fits.getdata(dirtyim, ext=0))[:,:,0:L]
#print(dirtyfits)
a=EasyMuffin(dirty=dirtyfits,psf=psffits)

a.loop(niter)

#print(dirtyim)
#print(psfim)
#print(niter)
