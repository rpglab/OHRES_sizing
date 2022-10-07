# -*- coding: utf-8 -*-
"""
Created on Mon June 20 15:42:20 2022

@author: Cunzhi Zhao
RPG Lab 
University of Houston
"""


from pyomo.environ import *
import pandas as pd
import numpy as np
#import gurobipy

# instance the pyomo abstract model
ResilenceHour = [3,6,9,12,15,18,21,24] # refers to resilience duration T^R 
ResultData = np.zeros((8,8))
for a in range(8):
    RA = ResilenceHour[a]
    model = AbstractModel()
    
    ### set
    model.PERIOD = Set()
    
    
    ### Constant Parameters
    model.WT_Cost = Param(default=20000000)  # wind turbine unit cost
    model.BESS_Cost = Param(default=350)    #unit cost /kwh
    model.El_Cost = Param(default=1200)     # electrolyzer cost /kwh
    model.Comp_Cost = Param(default=40)     # hydrogen compressor cost /kwh
    model.H2_kwh = Param(default=33)        # hydrogen per kilogram to kwh
    model.FC_Cost = Param(default=1000)     # fuel cell
    model.Cav = Param(default=35) # $/kg   
    model.WT_OM_Cost = Param(default=42000)   # O&M cost per year
    model.BESS_OM_Cost = Param(default=10)    # O&M cost per kwh per year
    model.El_OM_Cost = Param(default=0.02)   # O&M cost per kwh
    model.FC_OM_Cost = Param(default=0.013)  # O&M cost per kwh
    model.Cav_OM_Cost = Param(default = 44783)  # O&M cost per year
    model.BESSdegra =Param(default = 0.05)   # degradation cost factor
    model.El_effi =Param(default=0.7) # electrolyzer efficiency 
    model.FC_effi =Param(default=0.6) # fuel cell efficiency
    model.BESS_effi = Param(default=0.95) #BESS efficiency
    model.lifetime = Param(default=20) # lifetime period
    model.T_R = Param(default=RA) # resilence duration
    
    
    ### period parameters
    model.Time_TotalPd = Param(model.PERIOD)
    model.WT_Ava = Param(model.PERIOD)
    model.BigM = Param(default = 1000)
    
    ### Variables
    
    model.USCHARGE = Var(model.PERIOD, within =Binary) # BESS charge status 1 or 0
    model.USDISCHARGE = Var(model.PERIOD, within =Binary) # BESS discharge status 1 or 0
    model.PCHARGE = Var(model.PERIOD) #BESS charge power
    model.PDISCHARGE = Var(model.PERIOD) #BESS discharge power
    model.WT = Var(within= NonNegativeIntegers) # planning number of Wind turbine units 
    model.BESS =  Var(within= PositiveReals) # BESS planning size kwh
    model.El =  Var(within= PositiveReals) # electrolyzer planning size kwh
    model.FC =  Var(within= PositiveReals) # fuel cell planning size kwh
    model.Cavern =  Var(within= PositiveReals) # salt cavern size kg
    model.P_FC = Var(model.PERIOD) # fuel cell power output
    model.P_El = Var(model.PERIOD) # electrolyzer output
    model.P_Curt = Var(model.PERIOD, within= NonNegativeReals) # curtailment 
    model.ESSinitial = Var() # BESS initial
    model.ESS = Var(model.PERIOD) # BESS SOC 
    model.Cav_lvl = Var(model.PERIOD) # hydrogen level modeled similiar with BESS
    model.Cavinitial = Var() # initial hydrogen level
    model.Operation = Var() # operation cost
    
    ###objective function
    def objfunction(model):
        totalcost = model.WT*(model.WT_Cost + model.WT_OM_Cost*model.lifetime) + model.BESS*(model.BESS_Cost(1+model.BESSdegra*model.lifetime)+ model.BESS_OM_Cost*model.lifetime) + \
            model.El*(model.El_Cost*(1 + model.El_OM_Cost*model.lifetime) + model.Comp_Cost) + model.FC*model.FC_Cost*(1 + model.FC_OM_Cost*model.lifetime) + \
                model.Cavern*model.Cav + model.Cav_OM_Cost*model.lifetime
        return totalcost
    model.Cost = Objective(rule = objfunction, sense = minimize)
    
    ### Constrains
    #power balance
    
    def powerbalance(model,j):
        power = model.PDISCHARGE[j] + model.WT*model.WT_Ava[j] + model.P_FC[j]
        power = power - (model.Time_TotalPd[j] + model.P_El[j] + model.PCHARGE[j] + model.P_Curt[j])
        return  power == 0
    model.Cons_powerblance = Constraint(model.PERIOD, rule = powerbalance)
    
    ### BESS 
    def ESSbalance(model,j):
        if j >=2:    
            expr = model.ESS[j] -model.ESS[j-1] + model.PDISCHARGE[j]/model.BESS_effi - model.PCHARGE[j]*model.BESS_effi
            return expr ==0
        else:
            return Constraint.Skip
    model.Cons_ESSBalance = Constraint(model.PERIOD, rule = ESSbalance)
    
    def ESSinitial1(model, j):
        expr = model.ESS[1] -model.ESSinitial + model.PDISCHARGE[1]/model.BESS_effi-model.PCHARGE[1]*model.BESS_effi
        return expr == 0
    model.Cons_ESSinitial1 = Constraint(model.PERIOD, rule = ESSinitial1)
    
    def ESSinitial2(model, j):
        expr = 0.5*model.BESS - model.ESSinitial 
        return expr == 0
    model.Cons_ESSinitial2 = Constraint(model.PERIOD, rule = ESSinitial2)
    
    def ESSkeepon(model,j):
        expr =  model.USCHARGE[j] + model.USDISCHARGE[j]
        return expr <= 1
    model.Cons_ESSKeepon = Constraint(model.PERIOD, rule = ESSkeepon)
    
    def Essend(model, j):
        expr = model.ESS[24]
        return expr == model.ESSinitial
    model.Cons_Essend = Constraint(model.PERIOD, rule = Essend)
    
    def Esslimit1(model,j):
        return  model.ESS[j] <= model.BESS
    model.Cons_ESSlimit1 = Constraint(model.PERIOD,rule = Esslimit1)
    
    def Esslimit2(model,j):
        return 0 <= model.ESS[j]
    model.Cons_ESSlimit2 = Constraint(model.PERIOD,rule = Esslimit2)
    
    def PCHARGElimit1(model,j):
        return model.USCHARGE[j]*0 <= model.PCHARGE[j] 
    model.Cons_PCHARGElimit1 = Constraint(model.PERIOD,rule = PCHARGElimit1)
    
    def PCHARGElimit2(model,j):
        return  model.PCHARGE[j] <= model.USCHARGE[j]*0.25*model.BESS
    model.Cons_PCHARGElimit2 = Constraint(model.PERIOD,rule = PCHARGElimit2)
    
    def PDISCHARGElimit1(model,j):
        return model.USDISCHARGE[j]*0 <= model.PDISCHARGE[j] 
    model.Cons_PDISCHARGElimit1 = Constraint(model.PERIOD,rule = PDISCHARGElimit1)
    
    def PDISCHARGElimit2(model,j):
        return model.PDISCHARGE[j] <= model.USDISCHARGE[j]*0.25*model.BESS
    model.Cons_PDISCHARGElimit2 = Constraint(model.PERIOD,rule = PDISCHARGElimit2)
    
    #### Cavern for HESS
    
    def Cavbalance(model,j):
        if j >=2:    
            expr = model.Cav_lvl[j] -model.Cav_lvl[j-1] + model.P_FC[j]/model.FC_effi - model.P_El[j]*model.El_effi
            return expr ==0
        else:
            return Constraint.Skip
    model.Cons_CavBalance = Constraint(model.PERIOD, rule = Cavbalance)
    
    def Cavinitial1(model, j):
        expr = model.Cav_lvl[1] -model.Cavinitial + model.P_FC[1]/model.FC_effi - model.P_El[1]*model.El_effi
        return expr == 0
    model.Cons_Cavinitial1 = Constraint(model.PERIOD, rule = Cavinitial1)
    
    def Cavinitial2(model, j):
        expr = 0.5*model.Cavern - model.Cavinitial 
        return expr == 0
    model.Cons_Cavinitial2 = Constraint(model.PERIOD, rule = Cavinitial2)
    
    def CavernEnd(model, j):
        expr = model.Cav_lvl[24]
        return expr == model.Cavinitial
    model.Cons_CavernEnd= Constraint(model.PERIOD, rule = CavernEnd)
    
    def Cavlimit1(model,j):
        return  model.Cav_lvl[j] <= model.Cavern
    model.Cons_Cavlimit1 = Constraint(model.PERIOD,rule = Cavlimit1)
    
    def Cavlimit2(model,j):
        return 0 <= model.Cav_lvl[j]
    model.Cons_Cavlimit2 = Constraint(model.PERIOD,rule = Cavlimit2)
    
    ### fuel cell #####
    def PFC1(model,j):
        return 0 <= model.P_FC[j] 
    model.Cons_PFC1 = Constraint(model.PERIOD,rule = PFC1)   
    
    def PFC2(model,j):
        return  model.P_FC[j] <= model.FC
    model.Cons_PFC2 = Constraint(model.PERIOD,rule = PFC2)
    
    ### electrolyzer####
    def PEl1(model,j):
        return 0 <= model.P_El[j] 
    model.Cons_PEl1 = Constraint(model.PERIOD,rule = PEl1)
    
    def PEl2(model,j):
        return model.P_El[j] <= model.El
    model.Cons_PEl2= Constraint(model.PERIOD,rule = PEl2)
    
    def PEl3(model,j):
        return model.El*24*model.El_effi >= model.Cavern
    model.Cons_PEl3= Constraint(model.PERIOD,rule = PEl3)
    
    
    ## Resilience Models ### A
    # def Resilience1(model):
    #     return 0.25*model.BESS >= 60251
    # model.Cons_Resilience1= Constraint(rule = Resilience1)
    
    # def Resilience2(model):
    #     return model.BESS*model.BESS_effi >= 50000*model.T_R
    # model.Cons_Resilience2= Constraint(rule = Resilience2)
    
    ### Resilience Models ### B
    # def Resilience1(model):
    #     return model.FC >= 60251
    # model.Cons_Resilience1= Constraint(rule = Resilience1)
    
    # def Resilience2(model):
    #     return model.Cavern*model.FC_effi >= 50000*model.T_R
    # model.Cons_Resilience2= Constraint(rule = Resilience2)
    
    # Resilience Models ### C
    def Resilience1(model):
        return 0.25*model.BESS + model.FC >= 60251
    model.Cons_Resilience1= Constraint(rule = Resilience1)
    
    def Resilience2(model):
        return model.BESS*model.BESS_effi + model.Cavern*model.FC_effi >= 50000*model.T_R
    model.Cons_Resilience2= Constraint(rule = Resilience2)
    
    
    def OperationCost(model):
        expr = model.WT*model.WT_OM_Cost*model.lifetime + model.BESS*model.BESS_OM_Cost*model.lifetime + \
            model.El*model.El_Cost*( model.El_OM_Cost*model.lifetime) + model.FC*model.FC_Cost*(model.FC_OM_Cost*model.lifetime) + \
                + model.Cav_OM_Cost*model.lifetime
        return expr == model.Operation
    model.Constraint_OP_Cost = Constraint(rule = OperationCost)
    
    
    # instance according on the dat file
    SCUC_instance = model.create_instance('case16.dat')
    
    ### set the solver
    SCUCsolver = SolverFactory('gurobi')
    SCUCsolver.options.mipgap = 0.001
    results = SCUCsolver.solve(SCUC_instance)
    Data =[]
    Result =[]
    
    print("\nresults.Solution.Status: " + str(results.Solution.Status))
    print("\nresults.solver.status: " + str(results.solver.status))
    print("\nresults.solver.termination_condition: " + str(results.solver.termination_condition))
    print("\nresults.solver.termination_message: " + str(results.solver.termination_message))
    print('\nminimize cost: ' + str(SCUC_instance.Cost()))
    
    for j in SCUC_instance.PERIOD:
        X = [str(SCUC_instance.ESS[j]()/SCUC_instance.BESS()), str(SCUC_instance.PCHARGE[j]()),str(SCUC_instance.PDISCHARGE[j]()),str(SCUC_instance.Cav_lvl[j]()),str(SCUC_instance.P_FC[j]()),str(SCUC_instance.P_El[j]())]
        Data.append(X)
    
    Data = pd.DataFrame(Data, columns=['ESS_SOC', 'CHARGE', 'DISCHARGE','Cavern_lvl','FC','El'])
    print (Data)
    
    print('\Wind Turbin Amount: ' + str(SCUC_instance.WT()))
    print('\BESS Capacity: ' + str(SCUC_instance.BESS()) + ' kWh')
    print('\Eletrolyzer Power: ' + str(SCUC_instance.El()) + ' kW')
    print('\Fuel Cell power: ' + str(SCUC_instance.FC()) + ' kW')
    print('\Cavern Size: ' + str(SCUC_instance.Cavern()/40)+ ' kg')
    
    X = [SCUC_instance.WT(), SCUC_instance.BESS(),SCUC_instance.El(),SCUC_instance.FC(),SCUC_instance.Cavern()/SCUC_instance.H2_kwh(), \
              (SCUC_instance.Cost()-SCUC_instance.Operation())/1000000, SCUC_instance.Operation()/1000000,SCUC_instance.Cost()/1000000 ]
    ResultData[0,a] = SCUC_instance.WT()
    ResultData[1,a] = SCUC_instance.BESS()
    ResultData[2,a] = SCUC_instance.El()
    ResultData[3,a] = SCUC_instance.FC()
    ResultData[4,a] = SCUC_instance.Cavern()/SCUC_instance.H2_kwh()
    ResultData[5,a] = (SCUC_instance.Cost()-SCUC_instance.Operation())/1000000
    ResultData[6,a] = SCUC_instance.Operation()/1000000
    ResultData[7,a] = SCUC_instance.Cost()/1000000

