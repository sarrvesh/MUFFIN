# -*- coding: utf-8 -*-
"""
Created on Fri Oct 28 10:07:31 2016

@author: rammanouil
"""
import numpy as np
from scipy.fftpack import dct,idct
from deconv3d_tools import myfft2, myifft2, myifftshift
from deconv3d_tools import compute_tau_DWT, defadj, init_dirty_wiener, sat, heavy, rect
from deconv3d_tools import iuwt_decomp, iuwt_decomp_adj, dwt_decomp, dwt_recomp, dwt_I_decomp, dwt_I_recomp

str_cost="| {:5d} | {:6.6e} |"
str_cost_title="| {:5s} | {:12s} |\n"+"-"*24

str_cst_snr="| {:5d} | {:6.6e} | {:6.6e} |"
str_cst_snr_title="-"*39+"\n"+"| {:5s} | {:12s} | {:12s} |\n"+"-"*39

str_cost_wmsesure = "| {:5d} | {:6.6e} | {:6.6e} |"
str_cost_wmsesure_title = "-"*39+"\n"+"| {:5s} | {:12s} | {:12s} |\n"+"-"*39

str_cst_snr_wmse_wmsesure = "| {:5d} | {:6.6e} | {:6.6e} | {:6.6e} | {:6.6e} |"
str_cst_snr_wmse_wmsesure_title="-"*69+"\n"+"| {:5s} | {:12s} | {:12s} | {:12s} | {:12s} |\n"+"-"*69

str_cost_wmsesure_mu = "| {:5d} | {:6.6e} | {:6.6e} | {:6.6e} | {:6.6e} |"
str_cost_wmsesure_mu_title = "-"*69+"\n"+"| {:5s} | {:12s} | {:12s} | {:12s} | {:12s} |\n"+"-"*69

str_cst_snr_wmse_wmsesure_mu = "| {:5d} | {:6.6e} | {:6.6e} | {:6.6e} | {:6.6e} | {:6.6e} | {:6.6e} |"
str_cst_snr_wmse_wmsesure_mu_title="-"*99+"\n"+"| {:5s} | {:12s} | {:12s} | {:12s} | {:12s} | {:12s} | {:12s} |\n"+"-"*99

class EasyMuffin():
    def __init__(self,
                 mu_s=0.5,
                 mu_l=0.0,
                 mu_wiener = 5e1,
                 nb=(8,0),
                 tau = 1e-4,
                 sigma = 10,
                 var = 0,
                 dirtyinit=[],
                 dirty=[],
                 truesky=[],
                 psf=[],
                 fftw=0,
                 init=0,
                 fol_init=0,
                 save=0):

        if type(nb) is not tuple:
            print('nb must be a tuple of wavelets for dwt ')
            print('or a list of 2 integer for IUWT')
            print('first integer is the scale of decomposition (default:8)')
            print('second integer the scale or recomposition (default:0)')
            nb = (8,0)

        if mu_s< 0 :
            print('mu_s must be non negative, mu_s=.5')
            mu_s=0.5

        if mu_l< 0 :
            print('mu_l must be non negative, mu_l=0.')
            mu_l=0.0

        if tau< 0 :
            print('tau must be non negative, tau=1e-4')
            tau=1e-4

        if sigma< 0 :
            print('sigma must be positive, sigma=10.')
            sigma=10.

        #======================================================================
        # INITIALIZATION and INITIALIZATION FUNCTION1
        #======================================================================

        self.nb = nb
        self.mu_s = mu_s
        self.mu_l = mu_l
        self.sigma = sigma
        self.tau = tau
        self.dirtyinit = dirtyinit
        self.truesky = truesky
        self.psf = psf
        self.dirty=dirty
        self.var = var
        self.mu_wiener = mu_wiener
        self.fftw_flag = fftw
        self.init = init
        self.fol_init = fol_init
        self.save = save

        self.init_algo()

    def init_algo(self):
        """Initialization of the algorithm (all intermediate variables)"""
        
        if self.fftw_flag==0:
            self.fft2 = myfft2
            self.ifft2 = myifft2
        else:
            import pyfftw
            aa = pyfftw.empty_aligned(self.psf.shape,dtype='complex128')
            bb = pyfftw.empty_aligned(self.psf.shape,dtype='complex128')
            cc = pyfftw.empty_aligned(self.psf.shape,dtype='complex128')
            fft_object = pyfftw.FFTW(aa,bb,axes=(0,1),direction='FFTW_FORWARD',flags=('FFTW_MEASURE',),threads=10)
            ifft_object = pyfftw.FFTW(bb,cc,axes=(0,1),direction='FFTW_BACKWARD',flags=('FFTW_MEASURE',),threads=10)

            self.fft2 = fft_object
            self.ifft2 = ifft_object

        self.psfadj = defadj(self.psf)
        print('psf size ', self.psf.shape)
        print('drt size ', self.dirty.shape)

        # precomputations
        print('')
        print("precomputations...")
        self.nfreq = self.dirty.shape[2]
        self.nxy = self.dirty.shape[0]

        # x initialization 
        self.x = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
        
        if self.dirtyinit:
            self.x = self.dirtyinit
        elif self.init:
            print('')
            print('loading x_init from ',self.fol_init,' ... ')
            self.x = np.load(self.fol_init+'/x0_tst.npy')
        else:
            self.x = init_dirty_wiener(self.dirty, self.psf, self.psfadj, self.mu_wiener)

        # initializing alg. variables 
        self.hth_fft = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.complex)
        self.fty = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
        self.psfadj_fft = self.fft2(self.psfadj).copy(order='F')
        self.hth_fft = self.fft2( myifftshift( self.ifft2( self.psfadj_fft * self.fft2(self.psf) ) ) ).copy(order='F')
        tmp = myifftshift(self.ifft2(self.fft2(self.dirty)*self.psfadj_fft))
        self.fty = tmp.real.copy(order='F')
        self.wstu = np.zeros((self.nxy,self.nxy), dtype=np.float,order='F')
        self.Delta_freq = np.zeros((self.nxy,self.nxy), dtype=np.float,order='F')
        self.xtt = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
        self.xt = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')

        if type(self.nb[0]) == int:
            self.Decomp = iuwt_decomp
            self.Recomp = iuwt_decomp_adj ### adjoint pas recomp
            self.nbw_decomp = [f for f in range(self.nb[0])]
            self.nbw_recomp = self.nb[-1]
            self.tau = compute_tau_DWT(self.psf,self.mu_s,self.mu_l,self.sigma,self.nbw_decomp)
            print('')
            print('IUWT: tau = ', self.tau)
            print('')
        elif self.nb[-1] == 'I':
            self.Decomp = dwt_I_decomp
            self.Recomp = dwt_I_recomp
            self.nbw_decomp = self.nb
            self.nbw_recomp = self.nb
            self.tau = compute_tau_DWT(self.psf,self.mu_s,self.mu_l,self.sigma,self.nbw_decomp)
            print('')
            print('DWT+I: tau = ', self.tau)
            print('')
        else:
            self.Decomp = dwt_decomp
            self.Recomp = dwt_recomp
            self.nbw_decomp =self.nb
            self.nbw_recomp = self.nb
            self.tau = compute_tau_DWT(self.psf,self.mu_s,self.mu_l,self.sigma,self.nbw_decomp)
            print('')
            print('DWT: tau = ', self.tau)
            print('')

        self.utt = {}
        for freq in range(self.nfreq):
            self.utt[freq] = self.Decomp(np.zeros((self.nxy,self.nxy),dtype=np.float,order='F') , self.nbw_decomp)
        
        self.u = {}
        for freq in range(self.nfreq):
            self.u[freq] = self.Decomp(np.zeros((self.nxy,self.nxy),dtype=np.float,order='F') , self.nbw_decomp)
        if self.init:
            self.u = np.ndarray.tolist(np.load(self.fol_init+'/u.npy'))
        
        self.vtt = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
        self.v = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
        if self.init:
            self.v = np.load(self.fol_init+'/v.npy')

        self.nitertot = 0
        
        # Compute spatial and spectral scaling parameters 
        test = 0
        if test ==1:
            self.alpha_s = 1/(np.sum(np.sum(self.dirty**2,0),0)+1e-1) # col. vector
            self.alpha_l = 1/(np.sum(self.dirty**2,2)+1e-1) # image
            self.alpha_l = self.conv(self.alpha_l,np.ones((3,3)),'max').copy(order='F')
            self.alpha_s = self.alpha_s/self.alpha_s.max()
            self.alpha_l = self.alpha_l/self.alpha_l.max()
        else:
            self.alpha_s = np.ones(self.nfreq)
            self.alpha_l = np.ones((self.nxy,self.nxy))

        # compute cost & snr, psnr, wmse
        self.costlist = []
        self.costlist.append(self.cost())
        if any(self.truesky):
            self.snrlist = []
            self.truesky2 = np.sum(self.truesky*self.truesky)
            self.wmselist = []
            self.psnrlist = []
            self.psnrnum = np.sum((self.dirty-self.truesky)**2)/(self.nxy*self.nxy*self.nfreq)
            self.snrlist.append(self.snr())
            self.psnrlist.append(self.psnr())
            self.wmselist.append(self.wmse())
            print('The snr of the initialisation is ',self.snrlist[0])
            print('')

    def conv(self,x,y):
        tmp0 = self.fft2(x).copy(order='F')
        tmp = myifftshift(self.ifft2(tmp0*self.fft2(y)))
        return tmp.real
        
    def cost(self):
        """Compute cost for current iterate x"""
        #tmp = self.dirty - myifftshift(self.ifft2(self.fft2(self.x)*self.fft2(self.psf)))
        tmp = self.dirty - self.conv(self.x,self.psf)
        LS_cst = 0.5*(np.linalg.norm(tmp)**2)
        tmp = 0.
        for freq in range(self.nfreq):
            tmp1 = self.Decomp(self.x[:,:,freq],self.nbw_decomp)
            for b in self.nbw_decomp:
                tmp = tmp + np.sum(np.abs(tmp1[b]*self.alpha_s[freq]))
        Spt_cst = self.mu_s*tmp
        Spc_cst = self.mu_l*np.sum(np.abs(dct(self.x*self.alpha_l[...,None],axis=2,norm='ortho')))
        return (LS_cst + Spt_cst + Spc_cst)/(self.nxy*self.nxy*self.nfreq)

    def snr(self):
        resid = self.truesky - self.x
        return 10*np.log10(self.truesky2 / np.sum(resid*resid))

    def psnr(self):
        resid = (np.linalg.norm(self.conv(self.psf,self.truesky-self.x))**2)/(self.nxy*self.nxy*self.nfreq)
        return 10*np.log10(self.psnrnum / resid)

    def wmse(self):
        return (np.linalg.norm(self.conv(self.psf,self.truesky-self.x))**2)/(self.nxy*self.nxy*self.nfreq)
        
    def mse(self):
        return (np.linalg.norm(self.truesky-self.x)**2)/(self.nxy*self.nxy*self.nfreq)

   #======================================================================
   # MAIN Iteration - EASY MUFFIN
   #======================================================================
   
    def update(self):
        
        t = idct(self.v, axis=2, norm='ortho') # to check
        # compute gradient
        
        tmp = myifftshift( self.ifft2( self.fft2(self.x) *self.hth_fft ) )
        Delta_freq = tmp.real- self.fty
        
        for freq in range(self.nfreq):
            # compute iuwt adjoint
    
            wstu = self.Recomp(self.u[freq], self.nbw_recomp)
            # compute xt
            #print(self.alpha_l*t[:,:,freq].shape)
            #print(self.x[:,:,freq].shape)
            #print(self.xtt[:,:,freq].shape)
            
            self.xtt[:,:,freq] = self.x[:,:,freq] - self.tau*(Delta_freq[:,:,freq] + self.mu_s*self.alpha_s[freq]*wstu + self.mu_l*self.alpha_l*t[:,:,freq])
            
            self.xt[:,:,freq] = np.maximum(self.xtt[:,:,freq], 0.0, dtype=np.float )
            # update u
            tmp_spat_scal = self.Decomp(2*self.xt[:,:,freq] - self.x[:,:,freq] , self.nbw_decomp)
            for b in self.nbw_decomp:
                self.utt[freq][b] = self.u[freq][b] + self.sigma*self.mu_s*self.alpha_s[freq]*tmp_spat_scal[b]
                self.u[freq][b] = sat(self.utt[freq][b])
#            if freq==0:
#                print('wstu1:',np.linalg.norm(wstu))
#                print('xtt:',np.linalg.norm(self.xtt[:,:,freq] ))
#                print('xt:',np.linalg.norm(self.xt[:,:,freq] ))
#                print('')
        
        # update v
        self.vtt = self.v + self.sigma*self.mu_l*self.alpha_l[...,None]*dct(2*self.xt - self.x, axis=2, norm='ortho')
        self.v = sat(self.vtt)
        self.x = self.xt.copy(order='F')
        
#        print('x:',np.linalg.norm(self.x ))
#        print('xt:',np.linalg.norm(self.xt ))
            
        # compute cost snr, psnr, wmse if truesky given
        self.costlist.append(self.cost())
        if any(self.truesky):
            self.snrlist.append(self.snr())
            self.psnrlist.append(self.psnr())
            self.wmselist.append(self.wmse())

   #======================================================================
   # MAIN PROGRAM - EASY MUFFIN
   #======================================================================

    def loop(self,nitermax=10):
        """ main loop """
        if nitermax< 1:
            print('nitermax must be a positive integer, nitermax=10')
            nitermax=10
        
        # Iterations
        for niter in range(nitermax):
            self.update()
            if any(self.truesky):
                if (niter % 20) ==0:
                    print(str_cst_snr_title.format('It.','Cost','SNR'))
                print(str_cst_snr.format(niter,self.costlist[-1],self.snrlist[-1]))
            else:
                if (niter % 20) ==0:
                    print(str_cost_title.format('It.','Cost'))
                print(str_cost.format(niter,self.costlist[-1]))
                
        if self.save:
            np.save('x0_tst.npy',self.x)
            np.save('u.npy',self.u)
            np.save('v.npy',self.v)


class EasyMuffinSURE(EasyMuffin):

    def __init__(self,
                 mu_s=0.5,
                 mu_l=0.0,
                 mu_wiener = 5e1,
                 nb=(8,0),
                 tau = 1e-4,
                 sigma = 10,
                 var = 0,
                 dirtyinit=[],
                 dirty=[],
                 truesky=[],
                 psf=[],
                 step_mu = [0,0],
                 fftw = 0,
                 init=0,
                 fol_init=0,
                 save=0):

        super(EasyMuffinSURE,self).__init__(
                 mu_s,
                 mu_l,
                 mu_wiener,
                 nb,
                 tau,
                 sigma,
                 var,
                 dirtyinit,
                 dirty,
                 truesky,
                 psf,
                 fftw,
                 init,
                 fol_init,
                 save)
        
        self.step_mu = step_mu


    def init_algo(self):

            super(EasyMuffinSURE,self).init_algo()

            # compute Hn
            self.Hn = np.zeros((self.nxy,self.nxy,self.nfreq))
            np.random.seed(1)
            self.n = np.random.binomial(1,0.5,(self.nxy,self.nxy,self.nfreq))
            self.n[self.n==0] = -1
            self.Hn = self.conv(self.n,self.psfadj).copy(order='F')

            # init Jacobians
            self.Jv = np.zeros((self.nxy,self.nxy,self.nfreq))
            self.Jx = init_dirty_wiener(self.n, self.psf, self.psfadj, self.mu_wiener)
            self.Jxt = np.zeros((self.nxy,self.nxy,self.nfreq))
            self.Ju = {}
            for freq in range(self.nfreq):
                self.Ju[freq] = self.Decomp(np.zeros((self.nxy,self.nxy)) , self.nbw_decomp)

            # psnr, and wmse estimated using psure
            self.wmselistsure = []
            self.wmselistsure.append(self.wmsesure())

            if any(self.truesky):
                self.psnrlistsure = []
                self.psnrlistsure.append(self.psnrsure())

            # mu_s list
            self.mu_slist = []
            self.mu_slist.append(self.mu_s)

            # mu_l list
            self.mu_llist = []
            self.mu_llist.append(self.mu_l)

            # fdmc variables 
            self.sugarfdmclist = {}
            self.sugarfdmclist[0] = [0]
            self.sugarfdmclist[1] = [0]
            
            self.eps = 4*(self.var**0.5)*((self.nxy**2)**(-0.3)) # à verifier 
            np.random.seed(1)
            
            self.DeltaSURE = np.random.randn(self.nxy,self.nxy,self.nfreq)
            self.dirty2 = self.dirty + self.eps*self.DeltaSURE
        
            self.xt2 = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.u2 = {}
            for freq in range(self.nfreq):
                self.u2[freq] = self.Decomp(np.zeros((self.nxy,self.nxy)) , self.nbw_decomp)
            if self.init:
                self.u2 = np.ndarray.tolist(np.load(self.fol_init+'/u2.npy'))

            if self.dirtyinit:
                self.x2 = self.dirtyinit
            elif self.init:
                print('')
                print('loading x2_init from ',self.fol_init,' ... ')
                self.x2 = np.load(self.fol_init+'/x2.npy')
            else:
                self.x2 = init_dirty_wiener(self.dirty2, self.psf, self.psfadj, self.mu_wiener)

            self.v2 = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            if self.init:
                self.v2 = np.load(self.fol_init+'/v2.npy')
            
            self.fty2 = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            tmp = myifftshift(self.ifft2(self.fft2(self.dirty2)*self.psfadj_fft))
            self.fty2 = tmp.real.copy(order='F')
            
            self.xtt2 = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.utt2 = {}
            for freq in range(self.nfreq):
                self.utt2[freq] = self.Decomp(np.zeros((self.nxy,self.nxy)) , self.nbw_decomp)
            self.vtt2 = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.wmselistsurefdmc = []
            self.wmselistsurefdmc.append(self.wmsesurefdmc())
            
            self.dv_s = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.dx_s = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F') # init_dirty_wiener(self.n, self.psf, self.psfadj, self.mu_wiener)
            self.dxt_s = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.du_s = {}
            for freq in range(self.nfreq):
                self.du_s[freq] = self.Decomp(np.zeros((self.nxy,self.nxy)) , self.nbw_decomp)
                
            if self.init:
                self.dx_s = np.load(self.fol_init+'/dx_s.npy')
                self.dv_s = np.load(self.fol_init+'/dv_s.npy')
                self.du_s = np.ndarray.tolist(np.load(self.fol_init+'/du_s.npy'))
                
            self.dv_l = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.dx_l = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F') # init_dirty_wiener(self.n, self.psf, self.psfadj, self.mu_wiener)
            self.dxt_l = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.du_l = {}
            for freq in range(self.nfreq):
                self.du_l[freq] = self.Decomp(np.zeros((self.nxy,self.nxy), dtype=np.float,order='F') , self.nbw_decomp)
                
            if self.init:
                self.dx_l = np.load(self.fol_init+'/dx_l.npy')
                self.dv_l = np.load(self.fol_init+'/dv_l.npy')
                self.du_l = np.ndarray.tolist(np.load(self.fol_init+'/du_l.npy'))
                
            self.dv2_s = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.dx2_s = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F') # init_dirty_wiener(self.n, self.psf, self.psfadj, self.mu_wiener)
            self.dxt2_s = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.du2_s = {}
            for freq in range(self.nfreq):
                self.du2_s[freq] = self.Decomp(np.zeros((self.nxy,self.nxy), dtype=np.float,order='F') , self.nbw_decomp)
            
            if self.init:
                self.dx2_s = np.load(self.fol_init+'/dx2_s.npy')
                self.dv2_s = np.load(self.fol_init+'/dv2_s.npy')
                self.du2_s = np.ndarray.tolist(np.load(self.fol_init+'/du2_s.npy'))
            
            self.dv2_l = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.dx2_l = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F') # init_dirty_wiener(self.n, self.psf, self.psfadj, self.mu_wiener)
            self.dxt2_l = np.zeros((self.nxy,self.nxy,self.nfreq), dtype=np.float,order='F')
            self.du2_l = {}
            for freq in range(self.nfreq):
                self.du2_l[freq] = self.Decomp(np.zeros((self.nxy,self.nxy), dtype=np.float,order='F') , self.nbw_decomp)

            if self.init:
                self.dx2_l = np.load(self.fol_init+'/dx2_l.npy')
                self.dv2_l = np.load(self.fol_init+'/dv2_l.npy')
                self.du2_l = np.ndarray.tolist(np.load(self.fol_init+'/du2_l.npy'))
                
    def wmsesure(self):
        tmp = self.dirty - self.conv(self.x,self.psf)
        LS_cst = np.linalg.norm(tmp)**2/(self.nxy*self.nxy*self.nfreq)
        tmp = self.n*self.conv(self.Jx,self.psf)
        tmp = 2*(self.var/(self.nxy*self.nxy*self.nfreq))*(np.sum(tmp))
        return LS_cst - self.var + tmp

    def wmsesurefdmc(self):
        tmp = self.dirty - self.conv(self.x,self.psf)
        LS_cst = np.linalg.norm(tmp)**2
        tmp = ((self.conv(self.x2,self.psf) - self.conv(self.x,self.psf))*self.DeltaSURE)/self.eps              
        wmse = LS_cst - self.var*(self.nxy*self.nxy*self.nfreq) + 2*self.var*np.sum(tmp)
        
#       return LS_cst/(self.nxy*self.nxy*self.nfreq) - self.var + 2*(self.var/(self.nxy*self.nxy*self.nfreq))*(np.sum(tmp))

        return wmse/(self.nxy*self.nxy*self.nfreq)
        
    def psnrsure(self):
        return 10*np.log10(self.psnrnum/self.wmsesure())

    def update_jacobians(self):
        Jt = idct(self.Jv, axis=2,norm='ortho')
        # compute gradient
        tmp = myifftshift( self.ifft2( self.fft2(self.Jx) * self.hth_fft ) )
        JDelta_freq = tmp.real- self.Hn
        for freq in range(self.nfreq):
            # compute iuwt adjoint
            Js_l = self.Recomp(self.Ju[freq], self.nbw_recomp)
            # compute xt
            Jxtt = self.Jx[:,:,freq] - self.tau*(JDelta_freq[:,:,freq] + self.mu_s*self.alpha_s[freq]*Js_l + self.mu_l*self.alpha_l*Jt[:,:,freq])
            self.Jxt[:,:,freq] = heavy(self.xtt[:,:,freq])*Jxtt
            # update u
            tmp_spat_scal_J = self.Decomp(2*self.Jxt[:,:,freq] - self.Jx[:,:,freq] , self.nbw_decomp)
            for b in self.nbw_decomp:
                Jutt = self.Ju[freq][b] + self.sigma*self.mu_s*self.alpha_s[freq]*tmp_spat_scal_J[b]
                self.Ju[freq][b] = rect( self.utt[freq][b] )*Jutt
        # update v
        Jvtt = self.Jv + self.sigma*self.mu_l*self.alpha_l[...,None]*dct(2*self.Jxt - self.Jx, axis=2, norm='ortho')
        self.Jv = rect(self.vtt)*Jvtt
        self.Jx = self.Jxt.copy(order='F')
        # wmsesure
        self.wmselistsure.append(self.wmsesure())
        # psnrsure
        if any(self.truesky):
            self.psnrlistsure.append(self.psnrsure())
        
        return self.wmselistsure[-1]

    def loop(self,nitermax=10):
        """ main loop """

        if nitermax < 1:
            print('nitermax must be a positive integer, nitermax=10')
            nitermax=10
        for niter in range(nitermax):
            self.mu_slist.append(self.mu_s)
            self.mu_llist.append(self.mu_l)
            super(EasyMuffinSURE,self).update()
            self.update_jacobians()
            self.nitertot+=1

            if any(self.truesky):
                if (niter % 20) ==0:
                    print(str_cst_snr_wmse_wmsesure_title.format('It.','Cost','SNR','WMSE','WMSES'))
                #print(str_cst_snr_wmse_wmsesure.format(niter,self.costlist[-1],self.snrlist[-1],self.wmselist[-1],self.wmselistsure[-1]))
                print(str_cst_snr_wmse_wmsesure.format(niter,self.costlist[-1],self.snrlist[-1],self.wmselist[-1],self.wmselistsure[-1]))
            else:
                if (niter % 20) ==0:
                    print(str_cost_wmsesure_title.format('It.','Cost','WMSES'))
                print(str_cost_wmsesure.format(niter,self.costlist[-1],self.wmselistsure[-1]))
                
        if self.save:
            np.save('x0_tst.npy',self.x)
            np.save('u.npy',self.u)
            np.save('v.npy',self.v)


    # run update with y + eps*delta
    def update2(self):
        t = idct(self.v2, axis=2, norm='ortho') # to check
        # compute gradient
        tmp = myifftshift( self.ifft2( self.fft2(self.x2) *self.hth_fft ) )
        Delta_freq = tmp.real- self.fty2
        for freq in range(self.nfreq):
            # compute iuwt adjoint
            wstu = self.Recomp(self.u2[freq], self.nbw_recomp)
            # compute xt
            self.xtt2[:,:,freq] = self.x2[:,:,freq] - self.tau*(Delta_freq[:,:,freq] + self.mu_s*self.alpha_s[freq]*wstu + self.mu_l*self.alpha_l*t[:,:,freq])
            self.xt2[:,:,freq] = np.maximum(self.xtt2[:,:,freq], 0.0 )
            # update u
            tmp_spat_scal = self.Decomp(2*self.xt2[:,:,freq] - self.x2[:,:,freq] , self.nbw_decomp)
            for b in self.nbw_decomp:
                self.utt2[freq][b] = self.u2[freq][b] + self.sigma*self.mu_s*self.alpha_s[freq]*tmp_spat_scal[b]
                self.u2[freq][b] = sat(self.utt2[freq][b])
#            if freq==0:
#                print('wstu1:',np.linalg.norm(wstu))
#                print('xtt:',np.linalg.norm(self.xtt2[:,:,freq] ))
#                print('xt:',np.linalg.norm(self.xt2[:,:,freq] ))
#                print('')
                
        # update v
        self.vtt2 = self.v2 + self.sigma*self.mu_l*self.alpha_l[...,None]*dct(2*self.xt2 - self.x2, axis=2, norm='ortho')
        self.v2 = sat(self.vtt2)
        self.x2 = self.xt2.copy(order='F')       
        self.wmselistsurefdmc.append(self.wmsesurefdmc())
        
#        print('x:',np.linalg.norm(self.x2 ))
#        print('xt:',np.linalg.norm(self.xt2 ))

    def dx_mu(self):
        
        dt_s = idct(self.dv_s, axis=2, norm='ortho')
        
        # compute gradient
        tmp = myifftshift( self.ifft2( self.fft2(self.dx_s) *self.hth_fft ) )
        Delta_freq = tmp.real #- self.fty
        for freq in range(self.nfreq):

            # compute iuwt adjoint
            wstu = self.alpha_s[freq]*self.Recomp(self.u[freq], self.nbw_recomp) + self.mu_s*self.alpha_s[freq]*self.Recomp(self.du_s[freq], self.nbw_recomp)
            # compute xt
            dxtt_s = self.dx_s[:,:,freq] - self.tau*(Delta_freq[:,:,freq] + wstu + self.mu_l*self.alpha_l*dt_s[:,:,freq])
            self.dxt_s[:,:,freq] = heavy(self.xtt[:,:,freq] )*dxtt_s

            # update u
            tmp_spat_scal = self.Decomp(self.alpha_s[freq]*(2*self.xt[:,:,freq] - self.x[:,:,freq]) + self.mu_s*self.alpha_s[freq]*(2*self.dxt_s[:,:,freq] - self.dx_s[:,:,freq]), self.nbw_decomp)


            for b in self.nbw_decomp:
                dutt_s = self.du_s[freq][b] + self.sigma*tmp_spat_scal[b]
                self.du_s[freq][b] = rect(self.utt[freq][b])*dutt_s
                
#            if freq==0:
#                print('wstu1:',np.linalg.norm(wstu))
#                print('xtt:',np.linalg.norm(self.xtt[:,:,freq] ))
#                print('xt:',np.linalg.norm(self.dxt_s[:,:,freq] ))
#                print('')

        # update v
        dvtt_s = self.dv_s + self.sigma*self.mu_l*self.alpha_l[...,None]*dct(2*self.dxt_s - self.dx_s, axis=2, norm='ortho')
        self.dv_s = rect(self.vtt)*dvtt_s

        self.dx_s = self.dxt_s.copy(order='F')
        
#        print('x:',np.linalg.norm(self.dx_s ))

        dt_l = idct(self.dv_l*self.mu_l*self.alpha_l[...,None] + self.v*self.alpha_l[...,None], axis=2, norm='ortho')

        # compute gradient
        tmp = myifftshift( self.ifft2( self.fft2(self.dx_l) *self.hth_fft ) )
        Delta_freq = tmp.real #- self.fty
        for freq in range(self.nfreq):

            # compute iuwt adjoint
            wstu = self.mu_s*self.alpha_s[freq]*self.Recomp(self.du_l[freq], self.nbw_recomp)

            # compute xt
            dxtt_l = self.dx_l[:,:,freq] - self.tau*(Delta_freq[:,:,freq] + wstu + dt_l[:,:,freq])
            self.dxt_l[:,:,freq] = heavy(self.xtt[:,:,freq] )*dxtt_l

            # update u
            tmp_spat_scal = self.Decomp(self.mu_s*self.alpha_s[freq]*(2*self.dxt_l[:,:,freq] - self.dx_l[:,:,freq]), self.nbw_decomp)

            for b in self.nbw_decomp:
                dutt_l = self.du_l[freq][b] + self.sigma*tmp_spat_scal[b]
                self.du_l[freq][b] = rect(self.utt[freq][b])*dutt_l

        # update v
        dvtt_l = self.dv_l + self.sigma*self.mu_l*self.alpha_l[...,None]*dct(2*self.dxt_l - self.dx_l, axis=2, norm='ortho') + self.sigma*self.alpha_l[...,None]*dct(2*self.xt - self.x, axis=2, norm='ortho')
        self.dv_l = rect(self.vtt)*dvtt_l

        self.dx_l = self.dxt_l.copy(order='F')

        
    def dx2_mu(self):
        dt_s = idct(self.dv2_s, axis=2, norm='ortho')

        # compute gradient
        tmp = myifftshift( self.ifft2( self.fft2(self.dx2_s) *self.hth_fft ) )
        Delta_freq = tmp.real #- self.fty
        for freq in range(self.nfreq):

            # compute iuwt adjoint
            wstu = self.alpha_s[freq]*self.Recomp(self.u2[freq], self.nbw_recomp) + self.mu_s*self.alpha_s[freq]*self.Recomp(self.du2_s[freq], self.nbw_recomp)

            # compute xt
            dxtt_s = self.dx2_s[:,:,freq] - self.tau*(Delta_freq[:,:,freq] + wstu + self.mu_l*self.alpha_l*dt_s[:,:,freq])
            self.dxt2_s[:,:,freq] = heavy(self.xtt2[:,:,freq] )*dxtt_s

            # update u
            tmp_spat_scal = self.Decomp(self.alpha_s[freq]*(2*self.xt2[:,:,freq] - self.x2[:,:,freq]) + self.mu_s*self.alpha_s[freq]*(2*self.dxt2_s[:,:,freq] - self.dx2_s[:,:,freq]), self.nbw_decomp)

            for b in self.nbw_decomp:
                dutt_s = self.du2_s[freq][b] + self.sigma*tmp_spat_scal[b]
                self.du2_s[freq][b] = rect(self.utt2[freq][b])*dutt_s
                
#            if freq==0:
#                print('wstu1:',np.linalg.norm(wstu))
#                print('xtt:',np.linalg.norm(self.xtt2[:,:,freq] ))
#                print('xt:',np.linalg.norm(self.dxt2_s[:,:,freq] ))
#                print('')

        # update v
        dvtt2_s = self.dv2_s + self.sigma*self.mu_l*self.alpha_l[...,None]*dct(2*self.dxt2_s - self.dx2_s, axis=2, norm='ortho')
        self.dv2_s = rect(self.vtt2)*dvtt2_s

        self.dx2_s = self.dxt2_s.copy(order='F')
        
#        print('x:',np.linalg.norm(self.dx2_s ))

        dt_l = np.asfortranarray(idct(self.dv2_l*self.mu_l*self.alpha_l[...,None] + self.v2*self.alpha_l[...,None], axis=2, norm='ortho'))
#        print('1:',np.linalg.norm(self.dv2_l))
#        print('2:',np.linalg.norm(self.v2))
#        print('3:',np.linalg.norm(dt_l))

        # compute gradient
        tmp = myifftshift( self.ifft2( self.fft2(self.dx2_l) *self.hth_fft ) )
        Delta_freq = tmp.real #- self.fty
        
        for freq in range(self.nfreq):

            # compute iuwt adjoint
            wstu = self.mu_s*self.alpha_s[freq]*self.Recomp(self.du2_l[freq], self.nbw_recomp)
        
            # compute xt
            dxtt_l = self.dx2_l[:,:,freq] - self.tau*(Delta_freq[:,:,freq] + wstu + dt_l[:,:,freq])
            self.dxt2_l[:,:,freq] = heavy(self.xtt2[:,:,freq] )*dxtt_l

            # update u
            tmp_spat_scal = self.Decomp(self.mu_s*self.alpha_s[freq]*(2*self.dxt2_l[:,:,freq] - self.dx2_l[:,:,freq]), self.nbw_decomp)

            for b in self.nbw_decomp:
                dutt_l = self.du2_l[freq][b] + self.sigma*tmp_spat_scal[b]
                self.du2_l[freq][b] = rect(self.utt2[freq][b])*dutt_l
                
#            if freq==0:
#                print('4:',np.linalg.norm(dt_l[:,:,freq]))
#                print('')

        # update v
        dvtt2_l = self.dv2_l + self.sigma*self.mu_l*self.alpha_l[...,None]*dct(2*self.dxt2_l - self.dx2_l, axis=2, norm='ortho') + self.sigma*self.alpha_l[...,None]*dct(2*self.xt2 - self.x2, axis=2, norm='ortho')
        self.dv2_l = rect(self.vtt2)*dvtt2_l

        self.dx2_l = self.dxt2_l.copy(order='F')
        
        
    def sugarfdmc(self):

        tmp = 2*self.conv(self.psf,self.dx_s)*(self.conv(self.psf,self.x)-self.dirty) + 2*self.var*self.conv(self.psf,self.dx2_s-self.dx_s)*self.DeltaSURE/self.eps
        res1 = np.sum(tmp)/(self.nxy*self.nxy*self.nfreq)

        tmp = 2*self.conv(self.psf,self.dx_l)*(self.conv(self.psf,self.x)-self.dirty) + 2*self.var*self.conv(self.psf,self.dx2_l-self.dx_l)*self.DeltaSURE/self.eps
        res2 = np.sum(tmp)/(self.nxy*self.nxy*self.nfreq)
        
        self.sugarfdmclist[0].append(res1)
        self.sugarfdmclist[1].append(res2)
        
    def loop_fdmc(self,nitermax=10):
        
        if nitermax < 1:
            print('nitermax must be a positve integer, nitermax=10')
            nitermax=10
            
        for niter in range(nitermax):
            self.mu_slist.append(self.mu_s)
            self.mu_llist.append(self.mu_l)
            super(EasyMuffinSURE,self).update()
            self.update_jacobians()
            
            self.update2() # 
            self.dx_mu() # 
            self.dx2_mu() # 
            self.sugarfdmc()
            
            if niter>1 and niter%10==0:
                self.graddes_mu(self.step_mu) 
                if niter>1000 and niter%100==0:
                    self.step_mu = [tmp/1.2 for tmp in self.step_mu]
                
            self.nitertot+=1
            
            if self.truesky.any():
                if (niter % 20) ==0:
                    print(str_cst_snr_wmse_wmsesure_mu_title.format('It.','Cost','SNR','WMSE','WMSES','mu_s','mu_l'))
                print(str_cst_snr_wmse_wmsesure_mu.format(niter,self.costlist[-1],self.snrlist[-1],self.wmselist[-1],self.wmselistsurefdmc[-1],self.mu_slist[-1],self.mu_llist[-1]))
            else:
                if (niter % 20) ==0:
                    print(str_cost_wmsesure_mu_title.format('It.','Cost','WMSES','mu_s','mu_l'))
                print(str_cost_wmsesure_mu.format(niter,self.costlist[-1],self.wmselistsurefdmc[-1],self.mu_slist[-1],self.mu_llist[-1]))
                
        if self.save:
            np.save('x0_tst.npy',self.x)
            np.save('u.npy',self.u)
            np.save('v.npy',self.v)
            
            np.save('x2.npy',self.x2)
            np.save('u2.npy',self.u2)
            np.save('v2.npy',self.v2)
            
            np.save('dx_s.npy',self.dx_s)
            np.save('du_s.npy',self.du_s)
            np.save('dv_s.npy',self.dv_s)
            
            np.save('dx_l.npy',self.dx_l)
            np.save('du_l.npy',self.du_l)
            np.save('dv_l.npy',self.dv_l)
            
            np.save('dx2_s.npy',self.dx2_s)
            np.save('du2_s.npy',self.du2_s)
            np.save('dv2_s.npy',self.dv2_s)
            
            np.save('dx2_l.npy',self.dx2_l)
            np.save('du2_l.npy',self.du2_l)
            np.save('dv2_l.npy',self.dv2_l)

    def graddes_mu(self,step=[1e-3,1e-3]):
        self.mu_s = np.maximum(self.mu_s - step[0]*self.sugarfdmclist[0][-1],0)
        self.mu_l = np.maximum(self.mu_l - step[1]*self.sugarfdmclist[1][-1],0)
        
