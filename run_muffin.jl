using JLD
using FITSIO
using IUWT
using Wavelets

include("easy_muffinfunc.jl")

#num_simu = parse(Int, ARGS[1]) # for loop
num_simu = 2
μ_s = 0.3 #logspace(-3,0,10)[num_simu]

μ_λ = 0.0 #3.0
nb = 8
nitermax = 100
file_in = "tmp/m31_3d_3_conv"

β = 726.7135
τ = (1/2)*0.95/(β/2 + μ_s^2*8)

x, snr, cost = easy_muffin_dwt(τ, μ_s, μ_λ, nitermax, file_in)
#x, snr_c0 = easy_muffin_c0(μ_s, μ_λ, nb, nitermax, file_in)

#file_out = string("results/x_init_","$nitermax","_",@sprintf("%01.03f", μ_s),"_",@sprintf("%01.03f", μ_λ),".jld")
#JLD.save(file_out, "snr", snr,"μ_s",μ_s,"μ_λ",μ_λ)
