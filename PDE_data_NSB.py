from dolfin import *
from fenics import *
import numpy as np
from scipy import sparse
import sympy2fenics as sf
import matplotlib.pyplot as plt
import os

"""
FEniCS tutorial demo program: Poisson equation with Dirichlet conditions.
# -a(x,y) nalba u (x,y) = f ; u = g on gamma
# Formulation: Mixed formulation  u in L^2 sigma in H(div)
# Boundary conditions:  Natural    = True
#                       Essential  = False
# - tensor products
"""
def str2exp(s):
    return sf.sympy2exp(sf.str2sympy(s))
def coeff_extr(j,Hh,Usol):
    #This exctracts the coefficient of the different spaces
    # j is the index of the space:
    # j=0 the vector space for uh
    # j=1 the space for  component of sigma
    # For this to work the nature of the space has to be the same
    W  = Function(Hh)
    #Getting the exact DOF location
    DoF_map   = Hh.sub(j).dofmap()
    DoF_index = DoF_map.dofs()
    AUX1 = W.vector().get_local()    # empty DoF vector 
    AUX2 = Usol.vector().get_local() # All DoF
    AUX1[DoF_index] = AUX2[DoF_index]                # corresponding assignation
    W.vector().set_local(AUX1)       # corresponding assignation to empy vector
    coeff_vector = np.array(W.vector().get_local()) 
    return coeff_vector



def gen_dirichlet_data_NSB(z,mesh, Hh, example,i,d,train):
    parameters["form_compiler"]["representation"] = "uflacs"
    parameters["form_compiler"]["cpp_optimize"] = True
    parameters["form_compiler"]["quadrature_degree"] = 4
    parameters["allow_extrapolation"]= True
    parameters["refinement_algorithm"] = "plaza_with_parent_facets"


    fileO = XDMFFile("outputs/complexChannelFlow-AFW.xdmf")
    fileO.parameters["functions_share_mesh"] = True
    fileO.parameters["flush_output"] = True

    # ****** Constant coefficients ****** #

    f  = Constant((0,1))
    ndim = 2
    Id = Identity(ndim)

    lam = Constant(0.1)
    # *********** Variable coefficients ********** #

    #uinlet = Expression(('0','10.0*x[0]*(1.-x[0])'), degree = 2)
    #eta = Expression('0.1 + 0.01*sin(x[0])*sin(x[1])', degree=3)
    if example == 'other':
        pi     = str(3.14159265359)
        amean  = str(2)
        string = '1.89 + '
        for j in range(d):
            term   =  str(z[j])+ '*sin('+pi+'*(x+y)*('+str(j)+'+1) )/(pow('+str(j)+'+1.0,9/5))'
            string =  string + '+' + term
    string   =  '('+string+')' 
    mu       = Expression(str2exp(string), degree=3, domain=mesh)
    #mu = Expression('exp(-x[0]*x[1])', degree = 3)
    # *********** Variable coefficients ********** #

    uinlet = Expression(('0','1.0*x[0]*(1.-x[0])'), degree = 2)
    #eta    = Expression('0.1 + 0.01*sin(x[0])*sin(x[1])', degree=3)
    eta = Expression('0.1+x[0]*x[0]+x[1]*x[1]', degree=2)
    l      = 1 
    bdry = MeshFunction("size_t", mesh, "meshes/ComplexChannel_facet_region.xml")
    wall = 30; inlet=10; outlet=20;
    nn   = FacetNormal(mesh)
    tan  = as_vector((-nn[1],nn[0])) # DIMMMMMM     

    ds = Measure("ds", subdomain_data = bdry)
    dx = Measure("dx", domain=mesh)
    dS = Measure("dS", subdomain_data=bdry)
    # spaces to project for visualisation only
    Ph = FunctionSpace(mesh,'CG',1)
    Th = TensorFunctionSpace(mesh,'CG',1)


    #================================================================
    # Boundary condition
    #================================================================ 
    coeff_each_m_u =[]
    coeff_each_m_p =[]
    # *********** Trial and test functions ********** #

    Trial = TrialFunction(Hh)
    Sol   = Function(Hh)
    W_trainsol = Function(Hh)
    u,t_, sig1, sig2,gam_ = split(Sol)
    v,s_, tau1, tau2,del_ = TestFunctions(Hh)

    t = as_tensor(((t_[0], t_[1]),(t_[2],-t_[0])))
    s = as_tensor(((s_[0], s_[1]),(s_[2],-s_[0])))

    sigma = as_tensor((sig1,sig2))
    tau   = as_tensor((tau1,tau2))

    gamma = as_tensor(((0,gam_),(-gam_,0)))
    delta = as_tensor(((0,del_),(-del_,0)))
        
    # ********** Boundary conditions ******** #

    zero = Constant((0.,0.))
    #bcsig1 = DirichletBC(Hh.sub(4), zero, bdry, wall)
    #bcsig2 = DirichletBC(Hh.sub(5), zero, bdry, wall)
    #bcD = [bcsig1,bcsig2]

    nitsche = Constant(1.e4)
        
    # *************** Variational forms ***************** #
    a   = lam*mu*inner(t,s)*dx 
    b1  = - inner(sigma,s)*dx
    b   = - inner(outer(u,u),s)*dx
    b2  = inner(t,tau)*dx
    bbt = dot(u,div(tau))*dx + inner(gamma,tau)*dx
    bb  = dot(div(sigma),v)*dx + inner(sigma,delta)*dx
    cc  = eta * dot(u,v)*dx

    #+ xi*tr(tau+outer(v,v))*dx ???
    AA   = a + b1 + b2 + b + bbt + bb - cc 
    FF   = dot(tau*nn,uinlet)*ds(inlet) - dot(f,v)*dx
    Nonl = AA - FF + nitsche * dot((sigma+outer(u,u))*nn,tau*nn)*ds(outlet)
    #Nonl = AA - FF + nitsche * dot((sigma)*nn,tau*nn)*ds(outlet)

    Tangent = derivative(Nonl, Sol, Trial)
    Problem = NonlinearVariationalProblem(Nonl, Sol, J=Tangent)
    Solver  = NonlinearVariationalSolver(Problem)
    Solver.parameters['nonlinear_solver']                    = 'newton'
    Solver.parameters['newton_solver']['linear_solver']      = 'mumps'
    Solver.parameters['newton_solver']['absolute_tolerance'] = 1e-8
    Solver.parameters['newton_solver']['relative_tolerance'] = 1e-8
    Solver.parameters['newton_solver']['maximum_iterations'] = 25

    #set_log_level(LogLevel.ERROR)    
    Solver.solve()
    uh,th_, sigh1, sigh2,gamh_ = Sol.split()
    th = as_tensor(((th_[0], th_[1]),(th_[2],-th_[0])))
    sigmah = as_tensor((sigh1,sigh2))
    gammah = as_tensor(((0,gamh_),(-gamh_,0)))
    ph = project(-1/ndim*tr(sigmah + outer(uh,uh)),Ph) 
    coef_one_trial = uh.vector().get_local()
    coeff_each_m_u.append(coef_one_trial)
    coef_one_trial = ph.vector().get_local()
    coeff_each_m_p.append(coef_one_trial)
    
    if train:
        if i<0:
            plot(uh)
            filename = 'nonlinear_uh'+str(i)+'.png'
            plt.savefig ( filename )
            plt.close()
            plot(ph)
            filename = 'nonlinear_ph'+str(i)+'.png'
            plt.savefig ( filename )
            plt.close()
            folder1 = str('/home/sebanthalas/Documents/NE_NOV23/u_REA.pvd')
            vtkfile = File(folder1)
            vtkfile << uh
 

    
        

    
    norm_L4      = sqrt(sqrt(assemble( ((uh)**2)**2*dx)))
    norm_L2      = sqrt(assemble((ph)**2*dx))  # +  sqrt(assemble((div(Rsigh) )**2*dx) )  )

    


    return coeff_each_m_u,coeff_each_m_p, norm_L4, norm_L2


