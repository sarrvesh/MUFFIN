#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 17 15:03:34 2017

@author: rammanouil
"""

import numpy as np

from deconv3d_tools import defadj, init_dirty_wiener 
from deconv3d_tools import myfft2, myifft2, myifftshift, conv

str_cost="| {:5d} | {:6.6e} |"
str_cost_title="| {:5s} | {:12s} |\n"+"-"*24

str_cst_snr="| {:5d} | {:6.6e} | {:6.6e} |"
str_cst_snr_title="-"*39+"\n"+"| {:5s} | {:12s} | {:12s} |\n"+"-"*39

str_cost_wmsesure = "| {:5d} | {:6.6e} | {:6.6e} |"
str_cost_wmsesure_title = "-"*39+"\n"+"| {:5s} | {:12s} | {:12s} |\n"+"-"*39

str_cst_snr_wmse_wmsesure = "| {:5d} | {:6.6e} | {:6.6e} | {:6.6e} | {:6.6e} |"
str_cst_snr_wmse_wmsesure_title="-"*69+"\n"+"| {:5s} | {:12s} | {:12s} | {:12s} | {:12s}  |\n"+"-"*69
                
str_cost_wmsesure_mu = "| {:5d} | {:6.6e} | {:6.6e} | {:6.6e} |"
str_cost_wmsesure_mu_title = "-"*54+"\n"+"| {:5s} | {:12s} | {:12s} | {:12s} | {:12s} |\n"+"-"*54

str_cst_snr_wmse_wmsesure_mu = "| {:5d} | {:6.6e} | {:6.6e} | {:6.6e} | {:6.6e} | {:6.6e} |"
str_cst_snr_wmse_wmsesure_mu_title="-"*84+"\n"+"| {:5s} | {:12s} | {:12s} | {:12s} | {:12s} | {:12s} |\n"+"-"*84
                                
class Tikhonov():
    def __init__(self,
                 mu_s =5e-1,
                 eps_x = 1e-1,
                 var = 0,
                 dirtyinit =[],
                 dirty =[],
                 truesky =[],
                 psf =[]):

        #======================================================================
        # INITIALIZATION and INITIALIZATION FUNCTION
        #======================================================================
        self.mu_s = mu_s
        self.eps_x = eps_x
        self.dirtyinit = dirtyinit
        self.truesky = truesky
        self.psf = psf
        self.dirty=dirty
        self.var = var
        
        self.init_algo()

    def init_algo(self):
        """Initialization of te algorithm (all intermediate variables)"""

        self.psfadj = defadj(self.psf)
        print('psf size ', self.psf.shape)
        print('drt size ', self.dirty.shape)

        # precomputations
        print('')
        print("precomputations...")
        
        self.nxy = self.dirty.shape[0]
        if self.dirtyinit:
            self.x = self.dirtyinit
        else:
            self.x = init_dirty_wiener(self.dirty, self.psf, self.psfadj, 5e1)

        self.hth_fft = np.zeros((self.nxy,self.nxy), dtype=np.complex)
        self.fty = np.zeros((self.nxy,self.nxy), dtype=np.float)
        self.psfadj_fft = myfft2(self.psfadj)
        self.hth_fft = myfft2( myifftshift( myifft2( self.psfadj_fft * myfft2(self.psf) ) ) )
        tmp = myifftshift(myifft2(myfft2(self.dirty)*self.psfadj_fft))
        self.fty = tmp.real
        self.nitertot = 0

        # compute cost
        self.costlist = []
        self.costlist.append(self.cost())
        # snr, psnr, wmse
        if self.truesky.any():
            self.snrlist = []
            self.truesky2 = np.sum(self.truesky*self.truesky)
            self.wmselist = []
            self.psnrlist = []
            self.psnrnum = np.sum((self.dirty-self.truesky)**2)/(self.nxy*self.nxy)
        # compute snr if truesky given
        if self.truesky.any():
            self.snrlist.append(self.snr())
            self.psnrlist.append(self.psnr())
            self.wmselist.append(self.wmse())

    def cost(self):
        """Compute cost for current iterate x"""
        tmp = self.dirty - myifftshift(myifft2(myfft2(self.x)*myfft2(self.psf)))
        LS_cst = 0.5*(np.linalg.norm(tmp)**2)          
        tik_cst = 0.5*self.mu_s*np.linalg.norm(self.x)**2        
        return (LS_cst + tik_cst)/(self.nxy*self.nxy)

    def snr(self,change=True):
        if change:
            resid = self.truesky - self.x
            return 10*np.log10(self.truesky2 / np.sum(resid*resid))
        else:
            resid = self.truesky - self.x2_
            return 10*np.log10(self.truesky2 / np.sum(resid*resid))

    def psnr(self):
        resid = (np.linalg.norm(conv(self.psf,self.truesky-self.x))**2)/(self.nxy*self.nxy)
        return 10*np.log10(self.psnrnum / resid)

    def wmse(self):
        return (np.linalg.norm(conv(self.psf,self.truesky-self.x))**2)/(self.nxy*self.nxy)

    def mse(self):
        return (np.linalg.norm(self.truesky-self.x)**2)/(self.nxy*self.nxy)

    def update(self):
                
        tmp = myifftshift( myifft2( myfft2(self.x) *self.hth_fft ) ) 
        self.x = self.x - self.eps_x*(tmp.real + self.mu_s*self.x - self.fty)
        # compute cost
        self.costlist.append(self.cost())
        # compute snr, psnr, wmse if truesky given
        if self.truesky.any():
            self.snrlist.append(self.snr())
            self.psnrlist.append(self.psnr())
            self.wmselist.append(self.wmse())

    def loop(self,nitermax=10):
        """ main loop """

        if nitermax< 1:
            print('nitermax must be a positive integer, nitermax=10')
            nitermax=10
        # Iteration
        for niter in range(nitermax):
            self.update()            
            if self.truesky.any():
                if (niter % 20) ==0:
                    print(str_cst_snr_title.format('It.','Cost','SNR'))                    
                print(str_cst_snr.format(niter,self.costlist[-1],self.snrlist[-1]))
            else:
                if (niter % 20) ==0:
                    print(str_cost_title.format('It.','Cost'))                    
                print(str_cost.format(niter,self.costlist[-1]))

class TikhonovSURE(Tikhonov):

    def __init__(self,
                 mu_s=0.5,
                 eps_x = 1e-1,
                 eps_mu_s = 1e-1,
                 var = 0,
                 dirtyinit=[],
                 dirty=[],
                 truesky=[],
                 psf=[],
                 ):
        
        super(TikhonovSURE,self).__init__(
                 mu_s,
                 eps_x,
                 var,
                 dirtyinit,
                 dirty,
                 truesky,
                 psf,
                 ) 
        
        self.eps_mu_s = eps_mu_s

    def init_algo(self):

            super(TikhonovSURE,self).init_algo()

            # compute Hn
            self.Hn = np.zeros((self.nxy,self.nxy))
            np.random.seed(1)
            self.n = np.random.binomial(1,0.5,(self.nxy,self.nxy))
            self.n[self.n==0] = -1
            self.Hn = conv(self.n,self.psfadj)

            # init Jacobians w.r.t. y 
            self.Jx = init_dirty_wiener(self.n, self.psf, self.psfadj, 5e1)
            
            # init Jacobians w.r.t. mu_s 
            self.J_x = np.zeros((self.nxy,self.nxy))
            self.J_Dx = np.zeros((self.nxy,self.nxy))
            self.J_R = np.zeros((self.nxy,self.nxy))
            
            # psnr, and wmse estimated using psure
            self.wmselistsure = []
            self.wmselistsure.append(self.wmsesure())

            if self.truesky.any():
                self.psnrlistsure = []
                self.psnrlistsure.append(self.psnrsure())

            # mu_s list
            self.mu_slist = []
            self.mu_slist.append(self.mu_s)

    def wmsesure(self):
        tmp = self.dirty - conv(self.x,self.psf)
        LS_cst = np.linalg.norm(tmp)**2
        tmp = self.n*conv(self.Jx,self.psf)
        return LS_cst/(self.nxy*self.nxy) - self.var + 2*(self.var/(self.nxy*self.nxy))*(np.sum(tmp))
        
    def psnrsure(self):
        return 10*np.log10(self.psnrnum/self.wmsesure())

    def update_Jacobians(self):           
        # compute gradient
        tmp = myifftshift( myifft2( myfft2(self.Jx) * self.hth_fft ) )
        self.Jx = self.Jx - self.eps_x*(tmp.real + self.mu_s*self.Jx - self.Hn)
        # wmsesure
        self.wmselistsure.append(self.wmsesure())
        # psnrsure
        if self.truesky.any():
            self.psnrlistsure.append(self.psnrsure())
        
    def loop(self,nitermax=10):
        """ main loop """

        if nitermax < 1:
            print('nitermax must be a positive integer, nitermax=10')
            nitermax=10

        for niter in range(nitermax):
            self.mu_slist.append(self.mu_s)
            super(TikhonovSURE,self).update()
            self.update_Jacobians()
            self.nitertot+=1

            if self.truesky.any():
                if (niter % 20) ==0:
                    print(str_cst_snr_wmse_wmsesure_title.format('It.','Cost','SNR','WMSE','WMSES'))                    
                print(str_cst_snr_wmse_wmsesure.format(niter,self.costlist[-1],self.snrlist[-1],self.wmselist[-1],self.wmselistsure[-1]))
            else:
                if (niter % 20) ==0:
                    print(str_cost_wmsesure_title.format('It.','Cost','WMSES'))                    
                print(str_cost_wmsesure.format(niter,self.costlist[-1],self.wmselistsure[-1]))

    ## loop and compute sure
    def loop_mu_s(self,nitermax=10,change=True):
        """ main loop """

        if nitermax < 1:
            print('nitermax must be a positive integer, nitermax=10')
            nitermax=10

        for niter in range(nitermax):
            self.mu_slist.append(self.mu_s)
            super(TikhonovSURE,self).update()
            self.update_Jacobians()
            
            self.dJ_R_mu_s()
            
            if (niter>1) and (niter%1)==0 :
                self.GradDesc_mus()
                
            self.nitertot+=1

            if self.truesky.any():
                if (niter % 20) ==0:
                    print(str_cst_snr_wmse_wmsesure_mu_title.format('It.','Cost','SNR','WMSE','WMSES','mu_s'))                    
                print(str_cst_snr_wmse_wmsesure_mu.format(niter,self.costlist[-1],self.snrlist[-1],self.wmselist[-1],self.wmselistsure[-1],self.mu_slist[-1]))
            else:
                if (niter % 20) ==0:
                    print(str_cost_wmsesure_mu_title.format('It.','Cost','WMSES','mu_s'))                    
                print(str_cost_wmsesure_mu.format(niter,self.costlist[-1],self.wmselistsure[-1],self.mu_slist[-1]))
                
    def dJ_R_mu_s(self):       
        tmp = myifftshift( myifft2( myfft2(self.J_x) *self.hth_fft ) ) 
        self.J_x = self.J_x - self.eps_x*(tmp.real + self.mu_s*self.J_x + self.x)
        tmp = myifftshift( myifft2( myfft2(self.J_Dx) *self.hth_fft ) ) 
        self.J_Dx = self.J_Dx - self.eps_x*(tmp.real + self.mu_s*self.J_Dx + self.Jx)
        tmp = self.n*conv(self.J_Dx,self.psf)
        #self.J_R = -2*np.sum((self.dirty - conv(self.psf,self.x))*conv(self.psf,self.J_x)) + 2*self.var*np.trace(conv(self.psf,self.J_Dx))
        self.J_R = -2*np.sum((self.dirty - conv(self.psf,self.x))*conv(self.psf,self.J_x)) + 2*self.var*np.sum(tmp)
        #print(self.J_R)
    
    def GradDesc_mus(self):        
        self.mu_s = self.mu_s - self.eps_mu_s*self.J_R         
