import time as modutime

import os, fnmatch
import sys, datetime
import numpy as np
import pandas as pd
import scipy.interpolate
import scipy.stats

from tqdm import tqdm

import astroquery

import astropy
import astropy.coordinates
import astropy.units

import pickle
    
import celerite
#from celerite import terms


import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt

#import seaborn as sns

import tdpy
from tdpy.util import summgene

import lygos

import ephesus

"""
Given a target, miletos is an time-domain astronomy tool that allows 
1) automatic search for, download and process TESS and Kepler data via MAST or use user-provided data
2) impose priors based on custom inputs, ExoFOP or NASA Exoplanet Archive
3) model radial velocity and photometric time-series data on N-body systems
4) Make characterization plots of the target after the analysis
"""


def retr_lcurtess( \
                  
                  # global object
                  boolsrchmast, \

                  # keyword string for MAST search
                  strgmast=None, \
                  
                  # type of data to be retrieved
                  strgtypedata='obsd', \

                  # TIC ID
                  ticitarg=None, \

                  # RA for tesscut search
                  rasctarg=None, \
    
                  # DEC for tesscut search
                  decltarg=None, \
    
                  # Boolean flag to only consider FFI data
                  boolffimonly=False, \

                  # Boolean flag to only consider TPF data (2-min or 20-sec)
                  ## deprecated? to be deleted?
                  booltpxfonly=False, \

                  # name of the data product of lygos indicating which analysis has been used for photometry
                  nameanlslygo='psfn', \

                  ## Boolean flag to use 20-sec TPF when available
                  boolfasttpxf=True, \
                  
                  # a string label for the target to be optionally used for lygos if the target is identified with a RA&DEC
                  labltarg=None, \
                  
                  ## subset of sectors to retrieve
                  listtsecsele=None, \
                  
                  # input dictionary to lygos
                  dictlygoinpt=dict(), \
            
                  #Boolean flag to normalize the light curve by the median
                  boolnorm=None, \

                  ## Boolean flag to apply quality mask
                  boolmaskqual=True, \
         
                  # TPF light curve extraction pipeline (FFIs are always extracted by lygos)
                  ## 'lygos': lygos
                  ## 'SPOC': SPOC
                  typelcurtpxftess='lygos', \
                  
                  ## type of SPOC light curve: 'PDC', 'SAP'
                  typedataspoc='PDC', \
                  
                  # Boolean flag to diagnose the code using potentially computationally-expensive sanity checks, which may slow down the execution
                  booldiag=False, \

                  # type of verbosity
                  typeverb=1, \
                 ):
    '''
    Pipeline to retrieve TESS light curve of a target.
    '''
    
    #strgmast, rasctarg, decltarg = setp_coorstrgmast(rasctarg, decltarg, strgmast)
    
    print('Running the pipeline to retrieve the TESS light curve of the target...')

    if not (strgmast is not None and ticitarg is None and rasctarg is None and decltarg is None or \
            strgmast is None and ticitarg is not None and rasctarg is None and decltarg is None or \
            strgmast is None and ticitarg is None and rasctarg is not None and decltarg is not None):
                    print('strgmast')
                    print(strgmast)
                    print('ticitarg')
                    print(ticitarg)
                    print('rasctarg')
                    print(rasctarg)
                    print('decltarg')
                    print(decltarg)
                    raise Exception('')
    
    if boolnorm is not None and 'boolnorm' in dictlygoinpt:
        raise Exception('')
    
    if boolnorm is None:
        boolnorm = True
    
    ticitsec = None
    if strgmast is not None or ticitarg is not None:
        # determine the MAST keyword to be used for the target
        if strgmast is not None:
            strgmasttemp = strgmast
        if ticitarg is not None:
            strgmasttemp = 'TIC %d' % ticitarg
    
        maxmradisrchmast = 10. # arcsec
        strgradi = '%gs' % maxmradisrchmast
        
        # determine the TIC ID to be used to search for available sectors
        if ticitarg is None and not boolsrchmast:
            print('Will determine the TIC ID of the target using MAST keyword %s.' % strgmasttemp)
            print('Querying the TIC for sources within %s of %s...' % (strgradi, strgmasttemp))
            listdictticinear = astroquery.mast.Catalogs.query_object(strgmasttemp, catalog='TIC', radius=strgradi)
            boolsrchmast = True
            if len(listdictticinear) > 0 and listdictticinear[0]['dstArcSec'] < 1.:
                ticitsec = int(listdictticinear[0]['ID'])
            else:
                print('Warning! No TIC match to the MAST keyword: %s' % strgmasttemp)
        else:
            ticitsec = ticitarg
    
    if ticitsec is None:
        print('No TIC ID could be associated with the search.')
    else:
        print('TIC associated with the search is %d' % ticitsec)

    if rasctarg is not None:
        strgmasttemp = '%g %g' % (rasctarg, decltarg)

    print('typelcurtpxftess')
    print(typelcurtpxftess)
    
    if strgmast is not None or ticitarg is not None or rasctarg is not None:
        # get the list of sectors for which TESS data are available
        listtsectotl, temp, temp = ephesus.retr_listtsec(strgmasttemp)
    
        print('List of available sectors with TESS data:')
        print(listtsectotl)
    
    if ticitsec is not None:
        # get the list of sectors for which TESS SPOC data are available
        print('Retrieving the list of available TESS sectors for TIC ID %d for which there is SPOC light curve data...' % ticitsec)
        listtsec2min, listpath2min = ephesus.retr_tsecticibase(ticitsec)
        print('List of available sectors with high-cadence data:')
        print(listtsec2min)
    else:
        listpath2min = []

    print('temp: assuming no 20 second data!')
    listtsec20sc = []
    
    if typelcurtpxftess == 'lygos' or ticitsec is None or boolffimonly:
        listtseclygo = listtsectotl
        listtsecspoc = np.array([], dtype=int)
    else:
        listtseclygo = np.setdiff1d(listtsectotl, np.concatenate((listtsec2min, listtsec20sc)))
        listtsecspoc = listtsec2min
    
    print('List of sectors to be reduced via lygos')
    print(listtseclygo)
    print('List of sectors to be taken from SPOC')
    print(listtsecspoc)
    
    numbtsecspoc = listtsecspoc.size
    indxtsecspoc = np.arange(numbtsecspoc)

    # merge list of sectors whose light curves will come from SPOC and lygos, respectively
    listtsecmerg = np.unique(np.concatenate((listtseclygo, listtsecspoc)))

    # filter the list of sectors using the desired list of sectors, if any
    if listtsecsele is not None:
        print('List of sectors before filtering:')
        print(listtsecmerg)
        print('Filtering the list of sectors based on the user selection (listtsecsele)...')
        listtsec = []
        for tsec in listtsecsele:
            if tsec in listtsecmerg:
                listtsec.append(tsec)
        listtsec = np.array(listtsec)
    else:
        listtsec = listtsecmerg
    
    print('Final list of sectors to be retrieved:')
    print(listtsec)
    
    numbtsec = len(listtsec)
    indxtsec = np.arange(numbtsec)

    listtcam = np.empty(numbtsec, dtype=int)
    listtccd = np.empty(numbtsec, dtype=int)
    
    # determine for each sector whether a TFP is available
    booltpxf = ephesus.retr_booltpxf(listtsec, listtsecspoc)
    
    if typeverb > 0:
        print('booltpxf')
        print(booltpxf)
    
    if typelcurtpxftess == 'lygos':
        boollygo = np.ones(numbtsec, dtype=bool)
        booltpxflygo = not boolffimonly
        listtseclygo = listtsec
    if typelcurtpxftess == 'SPOC':
        boollygo = ~booltpxf
        booltpxflygo = False
        listtseclygo = listtsec[boollygo]
    listtseclygo = listtsec[boollygo]
    
    print('boollygo')
    print(boollygo)
    print('boolffimonly')
    print(boolffimonly)
    print('booltpxflygo')
    print(booltpxflygo)

    if typeverb > 0:
        print('booltpxflygo')
        print(booltpxflygo)
        print('listtseclygo')
        print(listtseclygo)
    
    dictlygooutp = None

    listarrylcur = [[] for o in indxtsec]
    if len(listtseclygo) > 0:
        
        dictlygoinpt['strgmast'] = strgmast
        dictlygoinpt['ticitarg'] = ticitarg
        dictlygoinpt['rasctarg'] = rasctarg
        dictlygoinpt['decltarg'] = decltarg
        dictlygoinpt['labltarg'] = labltarg
        dictlygoinpt['listipntsele'] = listtseclygo
        dictlygoinpt['booltpxflygo'] = booltpxflygo
        dictlygoinpt['listnameanls'] = 'psfn'
        if not 'boolmaskqual' in dictlygoinpt:
            dictlygoinpt['boolmaskqual'] = boolmaskqual
        if not 'boolnorm' in dictlygoinpt:
            dictlygoinpt['boolnorm'] = boolnorm
        
        if typeverb > 0:
            print('Will run lygos on the target...')
        dictlygooutp = lygos.main.init( \
                                       **dictlygoinpt, \
                                      )
        
        namearry = 'listarry' + nameanlslygo

        for o, tseclygo in enumerate(listtsec):
            indx = np.where(dictlygooutp['listtsec'] == tseclygo)[0]
            if indx.size > 0:
                indxtsecthis = indx[0]
                if len(dictlygooutp[namearry][indxtsecthis]) > 0:
                    
                    # choose the current sector
                    arry = dictlygooutp[namearry][indxtsecthis]
                    
                    # find good times
                    indxtimegood = np.where(np.isfinite(arry[:, 1]) & np.isfinite(arry[:, 2]))[0]
                    
                    # filter for good times
                    listarrylcur[o] = arry[indxtimegood, :]
                    
                    listtcam[o] = dictlygooutp['listtcam'][indxtsecthis]
                    listtccd[o] = dictlygooutp['listtccd'][indxtsecthis]
                    
    listarrylcursapp = None
    listarrylcurpdcc = None
    arrylcursapp = None
    arrylcurpdcc = None
    
    if typeverb > 0:
        print('listtsecspoc')
        print(listtsecspoc)
    if len(listtsecspoc) > 0 and typelcurtpxftess == 'SPOC':
        
        pathdatatess = os.environ['TESS_DATA_PATH'] + '/'
        # download data from MAST
        os.system('mkdir -p %s' % pathdatatess)
        
        if typeverb > 0:
            print('Checking if it is needed to download the relevant SPOC data products...')
        
        listhdundataspoc = [[] for o in indxtsecspoc]
        #listpathdownspoc = []

        # get observation tables
        #listtablobsv = retr_listtablobsv(strgmasttemp)
        #listprodspoc = []
        #for k, tablobsv in enumerate(listtablobsv):
        #    
        #    listprodspoctemp = astroquery.mast.Observations.get_product_list(tablobsv)
        #    
        #    if listtablobsv['distance'][k] > 0:
        #        continue

        #    strgdesc = 'Light curves'
        #    listprodspoctemp = astroquery.mast.Observations.filter_products(listprodspoctemp, description=strgdesc)
        #    for a in range(len(listprodspoctemp)):
        #        boolfasttemp = listprodspoctemp[a]['obs_id'].endswith('fast')
        #        if not boolfasttemp:
        #            tsec = int(listprodspoctemp[a]['obs_id'].split('-')[1][1:])
        #            listprodspoc.append(listprodspoctemp)
        #
        #for k in range(len(listprodspoc)):
        #    manifest = astroquery.mast.Observations.download_products(listprodspoc[k], download_dir=pathdatatess)
        #    
        #    # to move files to an upstream folder
        #    #pathnest = manifest['Local Path'][0]
        #    #pathnestfold = pathnest.split('/')[-1]
        #    #cmnd = 'mv %s %s' % (pathnest, pathdatatess)
        #    #print('cmnd')
        #    #print(cmnd)
        #    ##os.system(cmnd)
        #    #cmnd = 'rmdir %s' % (pathnestfold)
        #    #print('cmnd')
        #    #print(cmnd)
        #    ##os.system(cmnd)

        #    #listpathdownspoclcur.append(manifest['Local Path'][0])

        ## make sure the list of paths to sector files are time-sorted
        #listpathdownspoc.sort()
        #listpathdownspoclcur.sort()
        
        ## read SPOC light curves
        if typeverb > 0:
            if typedataspoc == 'SAP':
                print('Reading the SAP light curves...')
            else:
                print('Reading the PDC light curves...')
        listarrylcursapp = [[] for o in indxtsec] 
        listarrylcurpdcc = [[] for o in indxtsec] 
        for o in indxtsec:
            if not boollygo[o]:
                
                indx = np.where(listtsec[o] == listtsecspoc)[0][0]
                path = listpath2min[indx]
                listarrylcursapp[o], listtsec[o], listtcam[o], listtccd[o] = \
                                       ephesus.read_tesskplr_file(path, typeinst='tess', strgtypelcur='SAP_FLUX', \
                                                                                booldiag=booldiag, boolmaskqual=boolmaskqual, boolnorm=boolnorm)
                listarrylcurpdcc[o], listtsec[o], listtcam[o], listtccd[o] = \
                                       ephesus.read_tesskplr_file(path, typeinst='tess', strgtypelcur='PDCSAP_FLUX', \
                                                                                booldiag=booldiag, boolmaskqual=boolmaskqual, boolnorm=boolnorm)
                if typedataspoc == 'SAP':
                    arrylcur = listarrylcursapp[o]
                else:
                    arrylcur = listarrylcurpdcc[o]
                
                if booldiag:
                    if not np.isfinite(arrylcur).all():
                        print('')
                        print('')
                        print('')
                        print('boolnorm')
                        print(boolnorm)
                        print('boolmaskqual')
                        print(boolmaskqual)
                        print('arrylcur')
                        summgene(arrylcur)
                        raise Exception('')

                listarrylcur[o] = arrylcur
            
        # merge light curves from different sectors
        arrylcursapp = np.concatenate([arry for arry in listarrylcursapp if len(arry) > 0], 0)
        arrylcurpdcc = np.concatenate([arry for arry in listarrylcurpdcc if len(arry) > 0], 0)
    
    boolbadd = False
    for arrylcur in listarrylcur:
        if len(arrylcur) == 0:
            boolbadd = True

    if typeverb > 0:
        if numbtsec == 0:
            print('No data have been retrieved.')
        else:
            if numbtsec == 1:
                strgtemp = ''
            else:
                strgtemp = 's'
            print('%d sector%s of data retrieved.' % (numbtsec, strgtemp))
            print('listtsec')
            print(listtsec)
    
    if boolbadd:
        if typeverb > 0:
            print('listarrylcur contains at least one empty element (i.e., sector with no data). Will remove all such elements.')
        listarrylcurtemp = []
        listindxtsecgood = []
        for o in indxtsec:
            if len(listarrylcur[o]) > 0:
                listindxtsecgood.append(o)
        listindxtsecgood = np.array(listindxtsecgood, dtype=int)
        listtsec = listtsec[listindxtsecgood]
        listtcam = listtcam[listindxtsecgood]
        listtccd = listtccd[listindxtsecgood]
        for indxtsecgood in listindxtsecgood:
            listarrylcurtemp.append(listarrylcur[indxtsecgood])
        listarrylcur = listarrylcurtemp

    if len(listarrylcur) > 0:
        arrylcur = np.concatenate(listarrylcur, 0)
    else:
        arrylcur = []
    
    if typeverb > 0:
        for o, tsec in enumerate(listtsec):
            print('Sector %d has %d time samples' % (tsec, listarrylcur[o].shape[0]))

    for o, tsec in enumerate(listtsec):
        if len(listarrylcur[o]) == 0:
            print('o')
            print(o)
            print('listtsec')
            print(listtsec)
            print('listarrylcur')
            print(listarrylcur)
            print('listtsecspoc')
            print(listtsecspoc)
            print('listtseclygo')
            print(listtseclygo)
            print('tsec')
            print(tsec)
            raise Exception('')
        
        if not np.isfinite(listarrylcur[o][:, 1]).all():
            print('')
            print('Light curve relative flux is not all finite.')
            print('listtsec')
            print(listtsec)
            print('tsec')
            print(tsec)
            indxbadd = np.where(~np.isfinite(listarrylcur[o][:, 1]))[0]
            print('listarrylcur[o][:, 1]')
            summgene(listarrylcur[o][:, 1])
            print('indxbadd')
            summgene(indxbadd)
            raise Exception('')

    return arrylcur, arrylcursapp, arrylcurpdcc, listarrylcur, listarrylcursapp, listarrylcurpdcc, listtsec, listtcam, listtccd, listpath2min, dictlygooutp
   

def retr_lliknegagpro(listparagpro, lcur, objtgpro):
    '''
    Compute the negative loglikelihood of the GP model
    '''
    
    objtgpro.set_parameter_vector(listparagpro)
    
    return -objtgpro.log_likelihood(lcur)


def retr_gradlliknegagpro(listparagpro, lcur, objtgpro):
    '''
    Compute the gradient of the negative loglikelihood of the GP model
    '''
    
    objtgpro.set_parameter_vector(listparagpro)
    
    return -objtgpro.grad_log_likelihood(lcur)[1]


def pars_para_mile(para, gdat, strgmodl):
    
    dictparainpt = dict()
    
    gmod = getattr(gdat, strgmodl)
    
    #if gdat.typemodlener == 'full':
    #    dictparainpt['cons'] = para[gdat.dictindxpara['cons']]
    #else:
    #    for nameparabase in gmod.listnameparabase:
    #        strg = nameparabase + gdat.liststrgeneriter[gdat.indxdataiterthis[0]]
    #        if hasattr(gmod, strg):
    #            dictparainpt[strg] = getattr(gmod, strg)
    #        else:
    #            dictparainpt[strg] = para[gdat.dictindxpara[strg]]
    
    print('gmod.listnameparafullfixd')
    print(gmod.listnameparafullfixd)
    for name in gmod.listnameparafullfixd:
        #print('Found fixed value for parameter %s...' % name)
        dictparainpt[name] = getattr(gmod, name)
    
    print('gmod.listnameparafullflot')
    print(gmod.listnameparafullflot)
    for name in gmod.listnameparafullflot:
        
        dictparainpt[name] = para[gdat.dictindxpara[name]]
        
        if gdat.booldiag:
            if isinstance(gdat.dictindxpara[name], int) and gdat.dictindxpara[name] > 1e6 or \
                        not isinstance(gdat.dictindxpara[name], int) and (gdat.dictindxpara[name] > 1e6).any():
                print('name')
                print(name)
                print('gdat.dictindxpara[name]')
                print(gdat.dictindxpara[name])
                raise Exception('')
        
    if gmod.typemodl == 'psys' or gmod.typemodl == 'psyspcur':
        for name in ['radistar', 'masscomp', 'massstar']:
            dictparainpt[name] = None

    if gmod.typemodlbase == 'gpro':
        for name in ['sigmgprobase', 'rhoogprobase']:
            dictparainpt[name] = para[gdat.dictindxpara[name]]
        
    return dictparainpt


def retr_rflxmodl_mile_gpro(gdat, strgmodl, timemodl, dictparainpt, rflxmodl=None):
    
    dictobjtkern, dictobjtgpro = setp_gpro(gdat, dictparainpt, strgmodl)
    dictrflx = dict()
    for name in gdat.listnamecompgpro:
        dictrflx[name] = np.ones((timemodl.size, gdat.numbener))
        
        if name == 'supn' or name == 'excs':
            timeoffsdata = gdat.timethisfitt - dictparainpt['timesupn'] - gdat.timeoffs
            timeoffsmodl = timemodl - dictparainpt['timesupn'] - gdat.timeoffs
        if name == 'supn':
            indxtimedata = np.where(timeoffsdata > 0)[0]
            indxtimemodl = np.where(timeoffsmodl > 0)[0]
        if name == 'excs':
            indxtimedata = np.where((timeoffsdata > 0) & (timeoffsdata < 2.))[0]
            indxtimemodl = np.where((timeoffsmodl > 0) & (timeoffsmodl < 2.))[0]
        if name == 'totl':
            indxtimedata = np.arange(gdat.timethisfitt.size)
            indxtimemodl = np.arange(timemodl.size)
        
        if strgmodl == 'true':
            for e in gdat.indxenermodl:
                # compute the covariance matrix
                dictobjtgpro[name].compute(gdat.timethisfitt[indxtimedata])
                # get the GP model mean baseline
                dictrflx[name][indxtimemodl, e] = 1. + dictobjtgpro[name].sample()
                
        else:
            for e in gdat.indxenermodl:
                # compute the covariance matrix
                dictobjtgpro[name].compute(gdat.timethisfitt[indxtimedata], yerr=gdat.stdvrflxthisfittsele[indxtimedata, e])
                # get the GP model mean baseline
                dictrflx[name][indxtimemodl, e] = 1. + dictobjtgpro[name].predict(gdat.rflxthisfittsele[indxtimedata, e] - rflxmodl[indxtimedata, e], \
                                                                                                        t=timemodl[indxtimemodl], return_cov=False, return_var=False)
                
                #print('timemodl')
                #summgene(timemodl)
                #print('gdat.rflxthisfittsele')
                #summgene(gdat.rflxthisfittsele)
                #print('rflxmodl')
                #summgene(rflxmodl)
                #print('gdat.rflxthisfittsele')
                #summgene(gdat.rflxthisfittsele)
                #print('timemodl')
                #summgene(timemodl)

    return dictrflx


def retr_rvelmodl_mile(gdat, time, dictparainpt, strgmodl):
    
    gmod = getattr(gdat, strgmodl)

    dictrvelmodl = [[] for p in gdat.indxinst[1]]
    for p in gdat.indxinst[1]:
        dictrvelmodl[p] = retr_rvel(time[1][p], dictparainpt['epocmtracomp'], dictparainpt['pericomp'], dictparainpt['masscomp'], \
                                                dictparainpt['massstar'], dictparainpt['inclcomp'], dictparainpt['eccecomp'], dictparainpt['argupericomp'])

    return dictrvelmodl


def retr_rflxmodl_mile(gdat, time, dictparainpt, strgmodl):
    
    gmod = getattr(gdat, strgmodl)
    typemodl = gmod.typemodl
    
    dictrflxmodl = dict()

    if typemodl.startswith('psys') or typemodl == 'cosc':
        
        dictrflxmodl['totl'] = [[] for p in gdat.indxinst[0]]
        dictrflxmodl['tran'] = [[] for p in gdat.indxinst[0]]
        for p in gdat.indxinst[0]:
            if gdat.typemodlener == 'full':
                dictrflxmodl['totl'][p] = np.empty((time[0][p].size, gdat.numbener))
            else:
                dictrflxmodl['totl'][p] = np.empty((time[0][p].size, 1))
            dictrflxmodl['tran'][p] = np.empty_like(dictrflxmodl['totl'][p])
        
        timeredu = np.empty(gdat.numbenermodl)
        
        for ee, e in enumerate(gdat.indxenerthismodl):
        
            # temp
            pericomp = np.empty(gdat.numbcomp)
            rsmacomp = np.empty(gdat.numbcomp)
            epocmtracomp = np.empty(gdat.numbcomp)
            cosicomp = np.empty(gdat.numbcomp)
            if typemodl == 'cosc':
                masscomp = np.empty(gdat.numbcomp)
            
            for j in gmod.indxcomp:
                pericomp[j] = np.array([dictparainpt['pericom%d' % j]])
                rsmacomp[j] = np.array([dictparainpt['rsmacom%d' % j]])
                epocmtracomp = np.array([dictparainpt['epocmtracom%d' % j]])
                cosicomp = np.array([dictparainpt['cosicom%d' % j]])
            if typemodl == 'cosc':
                for j in gmod.indxcomp:
                    masscomp[j] = np.array([dictparainpt['masscom%d' % j]])
                massstar = dictparainpt['massstar']
                radistar = dictparainpt['massstar']
            else:
                masscomp = None
                massstar = None
                radistar = None
                
            if typemodl == 'cosc' or typemodl == 'supn':
                rratcomp = None
            elif 'rratcomp' in gmod.listnameparacomp:
                rratcomp = np.empty(gdat.numbcomp)
                for j in gmod.indxcomp:
                    print('dictparainpt')
                    print(dictparainpt)
                    rratcomp[j] = np.array([dictparainpt['rratcom%d%s' % (j, gdat.liststrgeneriter[gdat.indxdataiterthis[0]])]])
            
            for p in gdat.indxinst[0]:
            
                coeflmdklinr = dictparainpt['coeflmdklinr' + gdat.liststrgeneriter[e]]
                coeflmdkquad = dictparainpt['coeflmdkquad' + gdat.liststrgeneriter[gdat.indxdataiterthis[0]]]
                coeflmdk = np.array([coeflmdklinr, coeflmdkquad])
                
                if gdat.typemodllmdkener == 'line':
                    coeflmdk *= ratiline
                
                dictoutpmodl = ephesus.retr_rflxtranmodl(time, \
                                                         pericomp=pericomp, \
                                                         epocmtracomp=epocmtracomp, \
                                                         rsmacomp=rsmacomp, \
                                                         cosicomp=cosicomp, \
                                                         
                                                         massstar=massstar, \
                                                         radistar=radistar, \
                                                         masscomp=masscomp, \
                                                         
                                                         typelmdk='quadkipp', \
                                                         
                                                         booldiag=gdat.booldiag, \

                                                         coeflmdk=coeflmdk, \

                                                         typemodllens=gdat.typemodllens, \
                                                         
                                                         rratcomp=rratcomp, \
                                                         typesyst=typemodl, \
                                                         typeverb=0, \
                                                        )
            

                dictrflxmodl['tran'][p][:, ee] = dictoutpmodl['rflx']
                dictrflxmodl['totl'][p][:, ee] = dictoutpmodl['rflx']
            
            timeredu = dictoutpmodl['timeredu']

    if typemodl == 'supn':
        
        timeoffs = time - dictparainpt['timesupn'] - gdat.timeoffs
        indxpost = np.where(timeoffs > 0)[0]
        dflxsupn = np.zeros_like(time)
        
        if gmod.typemodlsupn == 'linr':
            dflxsupn[indxpost] = dictparainpt['coeflinesupn'] * timeoffs[indxpost] * 1e-3
        if gmod.typemodlsupn == 'quad':
            dflxsupn[indxpost] = dictparainpt['coeflinesupn'] * timeoffs[indxpost] * 1e-3 + dictparainpt['coefquadsupn'] * timeoffs[indxpost]**2 * 1e-3
        if gmod.typemodlsupn == 'cubc':
            dflxsupn[indxpost] = dictparainpt['coeflinesupn'] * timeoffs[indxpost] * 1e-3 + dictparainpt['coefquadsupn'] * timeoffs[indxpost]**2 * 1e-3 + \
                                                                                            dictparainpt['coefcubcsupn'] * timeoffs[indxpost]**3 * 1e-3
        dictrflxmodl['supn'] = 1. + dflxsupn[:, None]
        dictrflxmodl['totl'] = np.copy(dictrflxmodl['supn'])

        if gmod.typemodlexcs == 'bump':
            dictrflxmodl['excs'] = np.ones((time.size, gdat.numbener))
            if indxpost.size > 0:
                timeoffs = (time - dictparainpt['timesupn'] - dictparainpt['timebumpoffs'] - gdat.timeoffs) / dictparainpt['scalbump']
                indxpost = np.where(timeoffs > 0)[0]
                temp = timeoffs[indxpost]**2 * np.exp(-timeoffs[indxpost])
                #print('timeoffs')
                #summgene(timeoffs)
                #print('temp')
                #summgene(temp)
                #print('')
                #print('')
                #print('')
                temp /= np.amax(temp)
                dictrflxmodl['excs'][indxpost, 0] += dictparainpt['amplbump'] * temp * 1e-3
                dictrflxmodl['totl'] += dictrflxmodl['excs'] - 1.
        
        timeredu = None
                            
    # baseline
    if gmod.typemodlbase == 'cons':
        if gdat.typemodlener == 'full':
            dictrflxmodl['base'] = dictparainpt['cons'][None, :] * 1e-3
        else:
            dictrflxmodl['base'] = dictparainpt['cons' + gdat.liststrgeneriter[gdat.indxdataiterthis[0]]] * 1e-3
            dictrflxmodl['base'] = np.full((time.size, 1), dictrflxmodl['base'])
    if gmod.typemodlbase == 'step':
        rflxbase = np.zeros_like(dictrflxmodl['totl'])
        if gdat.typemodlener == 'full':
            consfrst = dictparainpt['consfrst'][None, :] * 1e-3
            consseco = dictparainpt['consseco'][None, :] * 1e-3
            timestep = dictparainpt['timestep'][None, :]
        
        else:
            consfrst = np.full((time.size, 1), dictparainpt['consfrst' + gdat.liststrgeneriter[gdat.indxdataiterthis[0]]]) * 1e-3
            consseco = np.full((time.size, 1), dictparainpt['consseco' + gdat.liststrgeneriter[gdat.indxdataiterthis[0]]]) * 1e-3
            timestep = np.full((time.size, 1), dictparainpt['timestep' + gdat.liststrgeneriter[gdat.indxdataiterthis[0]]])
            scalstep = np.full((time.size, 1), dictparainpt['scalstep' + gdat.liststrgeneriter[gdat.indxdataiterthis[0]]])
            
        dictrflxmodl['base'] = (consseco - consfrst) / (1. + np.exp(-(time[:, None] - timestep) / scalstep)) + consfrst
        
        #print('consfrst')
        #print(consfrst[0, 0])
        #print('timestep')
        #print(timestep[0, 0])
        #print('scalstep')
        #print(scalstep[0, 0])
        #print('consseco')
        #print(consseco[0, 0])
        #print('dictrflxmodl[base]')
        #summgene(dictrflxmodl['base'])
        #print('')

    if gmod.typemodlbase != 'gpro':
        # add baseline
        dictrflxmodl['totl'] += dictrflxmodl['base']
        dictrflxmodl['base'] += 1.
    
    #print('dictrflxmodl[base]')
    #summgene(dictrflxmodl['base'])
    #print('dictrflxmodl[supn]')
    #summgene(dictrflxmodl['supn'])
    #print('dictrflxmodl[totl]')
    #summgene(dictrflxmodl['totl'])
    #print('')
    #print('')
    #print('')
    #print('')
    #print('')
    #print('')
    #print('')
    
    if gdat.booldiag:
        if not np.isfinite(dictrflxmodl['totl']).all():
            raise Exception('')
        
    return dictrflxmodl, timeredu


def setp_gpro(gdat, dictparainpt, strgmodl):
    
    dictobjtkern = dict()
    dictobjtgpro = dict()

    gmod = getattr(gdat, strgmodl)
    
    ## construct the kernel object
    if gmod.typemodlbase == 'gpro':
        dictobjtkern['base'] = celerite.terms.Matern32Term(log_sigma=np.log(dictparainpt['sigmgprobase']*1e-3), log_rho=np.log(dictparainpt['rhoogprobase']))
    
    k = 0
    #print('gmod.typemodlbase')
    #print(gmod.typemodlbase)
    #print('strgmodl')
    #print(strgmodl)
    #print('dictobjtkern')
    #print(dictobjtkern)
    for name, valu in dictobjtkern.items():
        if k == 0:
            objtkerntotl = valu
        else:
            objtkerntotl += valu
        k += 1
    if dictobjtkern is not None:
        dictobjtkern['totl'] = objtkerntotl
    
    ## construct the GP model object
    for name in dictobjtkern:
        dictobjtgpro[name] = celerite.GP(dictobjtkern[name])
    
    return dictobjtkern, dictobjtgpro


def retr_llik_mile(para, gdat):
    
    """
    Return the likelihood.
    """
    
    dictparainpt = pars_para_mile(para, gdat, 'fitt')
    
    dictrflxmodl = retr_rflxmodl_mile(gdat, gdat.timethisfitt, dictparainpt, 'fitt')[0]
    dictrvelmodl = retr_rvelmodl_mile(gdat, gdat.timethisfitt, dictparainpt, 'fitt')
    
    if gdat.fitt.typemodl == 'supn' and (dictrflxmodl['supn'] < 1).any():
        return -np.inf

    if gdat.typemodlener == 'full':
        gdat.rflxthisfittsele = gdat.rflxthisfitt
        gdat.varirflxthisfittsele = gdat.varirflxthisfitt
        gdat.stdvrflxthisfittsele = gdat.stdvrflxthisfitt
    else:
        gdat.rflxthisfittsele = gdat.rflxthisfitt[:, gdat.indxenerthismodl]
        gdat.varirflxthisfittsele = gdat.varirflxthisfitt[:, gdat.indxenerthismodl]
        gdat.stdvrflxthisfittsele = gdat.stdvrflxthisfitt[:, gdat.indxenerthismodl]
    
    if gdat.booldiag:
        if gdat.rflxthisfittsele.ndim != dictrflxmodl['totl'].ndim:
            print('')
            print('gdat.rflxthisfittsele')
            summgene(gdat.rflxthisfittsele)
            print('dictrflxmodl[totl]')
            summgene(dictrflxmodl['totl'])
            raise Exception('')
        if gdat.rflxthisfittsele.shape[0] != dictrflxmodl['totl'].shape[0]:
            print('')
            print('gdat.rflxthisfittsele')
            summgene(gdat.rflxthisfittsele)
            print('dictrflxmodl[totl]')
            summgene(dictrflxmodl['totl'])
            raise Exception('')
        
    if gdat.typellik == 'gpro':
        
        llik = 0.
        
        for e in gdat.indxenermodl:
            
            resitemp = gdat.rflxthisfittsele[:, e] - dictrflxmodl['totl'][:, e]
            
            # construct a Gaussian Process (GP) model
            dictobjtkern, dictobjtgpro = setp_gpro(gdat, dictparainpt, 'fitt')
        
            # compute the covariance matrix
            dictobjtgpro['totl'].compute(gdat.timethisfitt, yerr=gdat.stdvrflxthisfittsele[:, e])
        
            # get the initial parameters of the GP model
            #parainit = objtgpro.get_parameter_vector()
            
            # get the bounds on the GP model parameters
            #limtparagpro = objtgpro.get_parameter_bounds()
            
            # minimize the negative loglikelihood
            #objtmini = scipy.optimize.minimize(retr_lliknegagpro, parainit, jac=retr_gradlliknegagpro, method="L-BFGS-B", \
            #                                                                                             bounds=limtparagpro, args=(lcurregi[indxtimeregioutt[i]], objtgpro))
            
            #print('GP Matern 3/2 parameters with maximum likelihood:')
            #print(objtmini.x)

            # update the GP model with the parameters that minimize the negative loglikelihood
            #objtgpro.set_parameter_vector(objtmini.x)
            
            # get the GP model mean baseline
            #lcurbase = objtgpro.predict(lcurregi[indxtimeregioutt[i]], t=timeregi, return_cov=False, return_var=False)#[0]
            
            # subtract the baseline from the data
            #lcurbdtrregi[i] = 1. + lcurregi - lcurbase

            #listobjtspln[i] = objtgpro
            #gp.compute(gdat.time[0], yerr=gdat.stdvrflxthisfittsele)
        
            llik += dictobjtgpro['totl'].log_likelihood(resitemp)
            
            #print('dictrflxmodl['totl'][:, e]')
            #summgene(dictrflxmodl['totl'][:, e])
            #print('resitemp')
            #summgene(resitemp)
            #print('dictobjtkern')
            #print(dictobjtkern)

    if gdat.typellik == 'sing':
        
        lliktemp = -0.5 * (gdat.rflxthisfittsele - dictrflxmodl['totl'])**2 / gdat.varirflxthisfittsele
        
        if gdat.boolrejeoutlllik:
            #lliktemp = np.sort(lliktemp.flatten())[1:]
            lliktemp[0, 0] -= np.amin(lliktemp)
        
        llik = np.sum(lliktemp)
    
    #print('gdat.typellik')
    #print(gdat.typellik)
    #print('dictrflxmodl')
    #for name in dictrflxmodl:
    #    print(name)
    #    summgene(dictrflxmodl[name])
    #print('gdat.stdvrflxthis')
    #summgene(gdat.stdvrflxthis)
    #print('gdat.rflxthisfittsele')
    #summgene(gdat.rflxthisfittsele)
    #print('gdat.varirflxthisfittsele')
    #summgene(gdat.varirflxthisfittsele)
    #print('')
    #print('')
    #print('')
    #print('')

    if gdat.booldiag:
        if gdat.typellik == 'sing' and llik.size != 1:
            print('gdat.typemodlener')
            print(gdat.typemodlener)
            print('gdat.rflxthisfittsele')
            summgene(gdat.rflxthisfittsele)
            print('dictrflxmodl[totl]')
            summgene(dictrflxmodl['totl'])
            print('gdat.varirflxthisfittsele')
            summgene(gdat.varirflxthisfittsele)
            print('llik')
            print(llik)
            raise Exception('')
        if not np.isfinite(llik):
            print('')
            print('gdat.typellik')
            print(gdat.typellik)
            print('dictparainpt')
            print(dictparainpt)
            print('gdat.varirflxthisfittsele')
            summgene(gdat.varirflxthisfittsele)
            print('gdat.rflxthisfittsele')
            summgene(gdat.rflxthisfittsele)
            print('gdat.typemodlener')
            print(gdat.typemodlener)
            raise Exception('')


    #print('para') 
    #print(para)
    #print('gdat.dictindxpara')
    #for strgtemp, valutemp in gdat.dictindxpara.items():
    #    print(strgtemp)
    #    print(valutemp)
    #print('dictparainpt')
    #print(dictparainpt)
    #print('llik')
    #print(llik)
    #print('')
    #print('')
    #print('')

    return llik


def retr_lliknega_mile(para, gdat):
    
    llik = retr_llik_mile(para, gdat)
    
    return -llik


def retr_dictderi_mile(para, gdat):
    
    dictparainpt = pars_para_mile(para, gdat, 'fitt')

    dictvarbderi = dict()
    dictrflxmodl = retr_rflxmodl_mile(gdat, gdat.timethisfittfine, dictparainpt, 'fitt')[0]
    for name in dictrflxmodl:
        dictvarbderi['rflxmodl%sfine' % name] = dictrflxmodl[name]
    dicttemp, dictvarbderi['timeredu'] = retr_rflxmodl_mile(gdat, gdat.timethisfitt, dictparainpt, 'fitt')
    dictvarbderi['rflxmodltotl'] = dicttemp['totl']
    
    if gdat.typellik == 'gpro':
        dictrflxfine = retr_rflxmodl_mile_gpro(gdat, 'fitt', gdat.timethisfittfine, dictparainpt, rflxmodl=dictvarbderi['rflxmodltotl'])
        dictrflx = retr_rflxmodl_mile_gpro(gdat, 'fitt', gdat.timethisfitt, dictparainpt, rflxmodl=dictvarbderi['rflxmodltotl'])
        
        for name in dictrflxfine:
            if name != 'totl':
                dictvarbderi['rflxmodl%sfine' % name] = dictrflxfine[name]
        
        dictvarbderi['rflxmodltotlfine'] += dictrflxfine['totl'] - 1.
        dictvarbderi['rflxmodltotl'] += dictrflx['totl'] - 1.
    
    dictvarbderi['rflxresi'] = gdat.rflxthisfitt[:, gdat.indxenerthismodl] - dictvarbderi['rflxmodltotl']

    dictvarbderi['stdvrflxresi'] = np.empty((gdat.numbrebn, gdat.numbener))
    for k in gdat.indxrebn:
        for e in gdat.indxenermodl:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    arry = np.zeros((dictvarbderi['rflxresi'][b][p][:, e].size, 3))
                    arry[:, 0] = gdat.timethisfitt
                    arry[:, 1] = dictvarbderi['rflxresi'][:, e][b][p]
                    delt = gdat.listdeltrebn[b][p][k]
                    arryrebn = ephesus.rebn_tser(arry, delt=delt)
                    dictvarbderi['stdvrflxresi'][k, e] = np.nanstd(arryrebn[:, 1])
                    
                    if gdat.booldiag:
                        if not np.isfinite(dictvarbderi['stdvrflxresi'][k, e]):
                            print('')
                            print('arry')
                            summgene(arry)
                            print('ephesus.rebn_tser(arry, delt=gdat.listdeltrebn[b][p][k])[:, 1]')
                            summgene(ephesus.rebn_tser(arry, delt=gdat.listdeltrebn[b][p][k])[:, 1])
                            raise Exception('')
    
    return dictvarbderi


def retr_llik_albbepsi(para, gdat):
    
    # Bond albedo
    albb = para[0]
    
    # heat recirculation efficiency
    epsi = para[2]

    psiimodl = (1 - albb)**.25
    #tmptirre = gdat.dictlist['tmptequi'][:, 0] * psiimodl
    tmptirre = gdat.gmeatmptequi * psiimodl
    
    tmptplandayy, tmptplannigh = retr_tmptplandayynigh(tmptirre)
    
    #llik = np.zeros(gdat.numbsamp)
    #llik += -0.5 * (tmptdayy - gdat.dictlist['tmptdayy'][:, 0])**2
    #llik += -0.5 * (tmptnigh - gdat.dictlist['tmptnigh'][:, 0])**2
    #llik += -0.5 * (psiimodl - gdat.listpsii)**2 * 1e6
    #llik = np.sum(llik)
    
    llik = 0.
    llik += -0.5 * (tmptdayy - gdat.gmeatmptdayy)**2 / gdat.gstdtmptdayy**2
    llik += -0.5 * (tmptnigh - gdat.gmeatmptnigh)**2 / gdat.gstdtmptnigh**2
    llik += -0.5 * (psiimodl - gdat.gmeapsii)**2 / gdat.gstdpsii**2 * 1e3
    
    return llik


def retr_modl_spec(gdat, tmpt, booltess=False, strgtype='intg'):
    
    if booltess:
        thpt = scipy.interpolate.interp1d(gdat.meanwlenband, gdat.thptband)(wlen)
    else:
        thpt = 1.
    
    if strgtype == 'intg':
        spec = tdpy.retr_specbbod(tmpt, gdat.meanwlen)
        spec = np.sum(gdat.diffwlen * spec)
    if strgtype == 'diff' or strgtype == 'logt':
        spec = tdpy.retr_specbbod(tmpt, gdat.cntrwlen)
        if strgtype == 'logt':
            spec *= gdat.cntrwlen
    
    return spec


def retr_llik_spec(para, gdat):
    
    tmpt = para[0]
    
    specboloplan = retr_modl_spec(gdat, tmpt, booltess=False, strgtype='intg')
    deptplan = 1e3 * gdat.rratmedi[0]**2 * specboloplan / gdat.specstarintg # [ppt]
    
    llik = -0.5 * np.sum((deptplan - gdat.deptobsd)**2 / gdat.varideptobsd)
    
    return llik


def writ_filealle(gdat, namefile, pathalle, dictalle, dictalledefa, typeverb=1):
    
    listline = []
    # add the lines
    if namefile == 'params.csv':
        listline.append('#name,value,fit,bounds,label,unit\n')
    
    if dictalle is not None:
        for strg, varb in dictalle.items():
            if namefile == 'params.csv':
                line = strg
                for k, varbtemp in enumerate(varb):
                    if varbtemp is not None:
                        line += ',' + varbtemp
                    else:
                        line += ',' + dictalledefa[strg][k]
                line += '\n'
            else:
                line = strg + ',' + varb + '\n'
            listline.append(line)
    for strg, varb in dictalledefa.items():
        if dictalle is None or strg not in dictalle:
            if namefile == 'params.csv':
                line = strg
                for varbtemp in varb:
                    line += ',' + varbtemp
                line += '\n'
            else:
                line = strg + ',' + varb + '\n'
            listline.append(line)
    
    # write
    pathfile = pathalle + namefile
    objtfile = open(pathfile, 'w')
    for line in listline:
        objtfile.write('%s' % line)
    if typeverb > 0:
        print('Writing to %s...' % pathfile)
    objtfile.close()


def get_color(color):

    if isinstance(color, tuple) and len(color) == 3: # already a tuple of RGB values
        return color

    import matplotlib.colors as mplcolors
    
    if color == 'r':
        color = 'red'
    if color == 'g':
        color = 'green'
    if color == 'y':
        color = 'yellow'
    if color == 'c':
        color = 'cyan'
    if color == 'm':
        color = 'magenta'
    if color == 'b':
        color = 'blue'
    if color == 'o':
        color = 'orange'
    hexcolor = mplcolors.cnames[color]

    hexcolor = hexcolor.lstrip('#')
    lv = len(hexcolor)
    
    return tuple(int(hexcolor[i:i + lv // 3], 16)/255. for i in range(0, lv, lv // 3)) # tuple of rgb values


def plot_pser(gdat, strgarry, boolpost=False, typeverb=1):
    
    for b in gdat.indxdatatser:
        arrypcur = gdat.arrypcur[strgarry]
        arrypcurbindtotl = gdat.arrypcur[strgarry+'bindtotl']
        if strgarry.startswith('prim'):
            arrypcurbindzoom = gdat.arrypcur[strgarry+'bindzoom']
        # plot individual phase curves
        for p in gdat.indxinst[b]:
            for j in gmod.indxcomp:
                
                path = gdat.pathimagtarg + 'pcurphas_%s_%s_%s_%s_%s.%s' % (gdat.liststrginst[b][p], gdat.liststrgcomp[j], \
                                                                                            strgarry, gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0., 0.3, 0.5, 0.1]})
                if not os.path.exists(path):
                    # phase on the horizontal axis
                    figr, axis = plt.subplots(1, 1, figsize=gdat.figrsizeydob)
                    if b == 0:
                        yerr = None
                    if b == 1:
                        yerr = arrypcur[b][p][j][:, 2]
                    axis.errorbar(arrypcur[b][p][j][:, 0], arrypcur[b][p][j][:, 1], yerr=yerr, elinewidth=1, capsize=2, zorder=1, \
                                                                color='grey', alpha=gdat.alphraww, marker='o', ls='', ms=1, rasterized=gdat.boolrastraww)
                    if b == 0:
                        yerr = None
                    if b == 1:
                        yerr = arrypcurbindzoom[b][p][j][:, 2]
                    axis.errorbar(arrypcurbindtotl[b][p][j][:, 0], arrypcurbindtotl[b][p][j][:, 1], color=gdat.listcolrcomp[j], elinewidth=1, capsize=2, \
                                                                                                                     zorder=2, marker='o', ls='', ms=3)
                    if gdat.boolwritplan:
                        axis.text(0.9, 0.9, r'\textbf{%s}' % gdat.liststrgcomp[j], \
                                            color=gdat.listcolrcomp[j], va='center', ha='center', transform=axis.transAxes)
                    axis.set_ylabel(gdat.listlabltser[b])
                    axis.set_xlabel('Phase')
                    # overlay the posterior model
                    if boolpost:
                        axis.plot(gdat.arrypcur[strgarry[:4]+'modltotl'+strgarry[-4:]][b][p][j][:, 0], \
                                        gdat.arrypcur[strgarry[:4]+'modltotl'+strgarry[-4:]][b][p][j][:, 1], color='b', zorder=3)
                    if gdat.listdeptdraw is not None:
                        for k in range(len(gdat.listdeptdraw)):  
                            axis.axhline(1. - 1e-3 * gdat.listdeptdraw[k], ls='-', color='grey')
                    if typeverb > 0:
                        print('Writing to %s...' % path)
                    plt.savefig(path)
                    plt.close()
            
                if strgarry.startswith('prim'):
                    # time on the horizontal axis
                    path = gdat.pathimagtarg + 'pcurtime_%s_%s_%s_%s_%s.%s' % (gdat.liststrginst[b][p], gdat.liststrgcomp[j], \
                                                                                    strgarry, gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.5, 0.2, 0.5, 0.1]})
                    if not os.path.exists(path):
                        figr, axis = plt.subplots(1, 1, figsize=gdat.figrsize)
                        if b == 0:
                            yerr = None
                        if b == 1:
                            yerr = arrypcur[b][p][j][:, 2]
                        axis.errorbar(gdat.pericompprio[j] * arrypcur[b][p][j][:, 0] * 24., arrypcur[b][p][j][:, 1], yerr=yerr, elinewidth=1, capsize=2, \
                                                            zorder=1, color='grey', alpha=gdat.alphraww, marker='o', ls='', ms=1, rasterized=gdat.boolrastraww)
                        if b == 0:
                            yerr = None
                        if b == 1:
                            yerr = arrypcurbindzoom[b][p][j][:, 2]
                        
                        if np.isfinite(gdat.duraprio[j]):
                            axis.errorbar(gdat.pericompprio[j] * arrypcurbindzoom[b][p][j][:, 0] * 24., arrypcurbindzoom[b][p][j][:, 1], zorder=2, \
                                                                                                        yerr=yerr, elinewidth=1, capsize=2, \
                                                                                                              color=gdat.listcolrcomp[j], marker='o', ls='', ms=3)
                        if boolpost:
                            axis.plot(gdat.pericompprio[j] * 24. * gdat.arrypcur[strgarry[:4]+'modltotl'+strgarry[-4:]][b][p][j][:, 0], \
                                                                                            gdat.arrypcur[strgarry[:4]+'modltotl'+strgarry[-4:]][b][p][j][:, 1], \
                                                                                                                            color='b', zorder=3)
                        if gdat.boolwritplan:
                            axis.text(0.9, 0.9, \
                                            r'\textbf{%s}' % gdat.liststrgcomp[j], color=gdat.listcolrcomp[j], va='center', ha='center', transform=axis.transAxes)
                        axis.set_ylabel(gdat.listlabltser[b])
                        axis.set_xlabel('Time [hours]')
                        if np.isfinite(gdat.duramask[j]):
                            axis.set_xlim([-np.nanmax(gdat.duramask), np.nanmax(gdat.duramask)])
                        if gdat.listdeptdraw is not None:
                            for k in range(len(gdat.listdeptdraw)):  
                                axis.axhline(1. - 1e-3 * gdat.listdeptdraw[k], ls='--', color='grey')
                        plt.subplots_adjust(hspace=0., bottom=0.25, left=0.25)
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        plt.savefig(path)
                        plt.close()
            
            if gdat.numbcomp > 1:
                # plot all phase curves
                path = gdat.pathimagtarg + 'pcurphastotl_%s_%s_%s_%s.%s' % (gdat.liststrginst[b][p], strgarry, \
                                                                                gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                if not os.path.exists(path):
                    figr, axis = plt.subplots(gdat.numbcomp, 1, figsize=gdat.figrsizeydob, sharex=True)
                    if gdat.numbcomp == 1:
                        axis = [axis]
                    for jj, j in enumerate(gmod.indxcomp):
                        axis[jj].plot(arrypcur[b][p][j][:, 0], arrypcur[b][p][j][:, 1], color='grey', alpha=gdat.alphraww, \
                                                                                            marker='o', ls='', ms=1, rasterized=gdat.boolrastraww)
                        axis[jj].plot(arrypcurbindtotl[b][p][j][:, 0], arrypcurbindtotl[b][p][j][:, 1], color=gdat.listcolrcomp[j], marker='o', ls='', ms=1)
                        if gdat.boolwritplan:
                            axis[jj].text(0.97, 0.8, r'\textbf{%s}' % gdat.liststrgcomp[j], transform=axis[jj].transAxes, \
                                                                                                color=gdat.listcolrcomp[j], va='center', ha='center')
                    axis[0].set_ylabel(gdat.listlabltser[b])
                    axis[0].set_xlim(-0.5, 0.5)
                    axis[0].yaxis.set_label_coords(-0.08, 1. - 0.5 * gdat.numbcomp)
                    axis[gdat.numbcomp-1].set_xlabel('Phase')
                    
                    plt.subplots_adjust(hspace=0., bottom=0.2)
                    if gdat.typeverb > 0:
                        print('Writing to %s...' % path)
                    plt.savefig(path)
                    plt.close()
    

def retr_albg(amplplanrefl, radicomp, smax):
    '''
    Return geometric albedo.
    '''
    
    albg = amplplanrefl / (radicomp / smax)**2
    
    return albg


def calc_feat(gdat, strgpdfn):

    gdat.liststrgfeat = ['epocmtracomp', 'pericomp', 'rratcomp', 'rsmacomp', 'cosicomp', 'ecos', 'esin', 'rvelsema']
    if strgpdfn == '0003' or strgpdfn == '0004':
        gdat.liststrgfeat += ['sbrtrati', 'amplelli', 'amplbeam']
    if strgpdfn == '0003':
        gdat.liststrgfeat += ['amplplan', 'timeshftplan']
    if strgpdfn == '0004':
        gdat.liststrgfeat += ['amplplanther', 'amplplanrefl', 'timeshftplanther', 'timeshftplanrefl']
    
    gdat.dictlist = {}
    gdat.dictpost = {}
    gdat.dicterrr = {}
    for strgfeat in gdat.liststrgfeat:
        gdat.dictlist[strgfeat] = np.empty((gdat.numbsamp, gdat.numbcomp))

        for j in gmod.indxcomp:
            if strgpdfn == 'prio' or strgpdfn in gdat.typepriocomp:
                mean = getattr(gdat, strgfeat + 'prio')
                stdv = getattr(gdat, 'stdv' + strgfeat + 'prio')
                if not np.isfinite(mean[j]):
                    continue

                gdat.dictlist[strgfeat][:, j] = mean[j] + np.random.randn(gdat.numbsamp) * stdv[j]
                if strgfeat == 'rratcomp':
                    gdat.dictlist[strgfeat][:, j] = tdpy.samp_gaustrun(gdat.numbsamp, mean[j], stdv[j], 0., np.inf)

            else:
                if strgfeat == 'epocmtracomp':
                    strg = '%s_epoch' % gdat.liststrgcomp[j]
                if strgfeat == 'pericomp':
                    strg = '%s_period' % gdat.liststrgcomp[j]
                if strgfeat == 'rratcomp':
                    strg = '%s_rr' % gdat.liststrgcomp[j]
                if strgfeat == 'rsmacomp':
                    strg = '%s_rsuma' % gdat.liststrgcomp[j]
                if strgfeat == 'cosicomp':
                    strg = '%s_cosi' % gdat.liststrgcomp[j]
    
                if strgpdfn == '0003' or strgpdfn == '0004':
                    if strgfeat == 'sbrtrati':
                        strg = '%s_sbratio_TESS' % gdat.liststrgcomp[j]
                    if strgfeat == 'amplbeam':
                        strg = '%s_phase_curve_beaming_TESS' % gdat.liststrgcomp[j]
                    if strgfeat == 'amplelli':
                        strg = '%s_phase_curve_ellipsoidal_TESS' % gdat.liststrgcomp[j]
                if strgpdfn == '0003':
                    if strgfeat == 'amplplan':
                        strg = '%s_phase_curve_atmospheric_TESS' % gdat.liststrgcomp[j]
                    if strgfeat == 'timeshftplan':
                        strg = '%s_phase_curve_atmospheric_shift_TESS' % gdat.liststrgcomp[j]
                if strgpdfn == '0004':
                    if strgfeat == 'amplplanther':
                        strg = '%s_phase_curve_atmospheric_thermal_TESS' % gdat.liststrgcomp[j]
                    if strgfeat == 'amplplanrefl':
                        strg = '%s_phase_curve_atmospheric_reflected_TESS' % gdat.liststrgcomp[j]
                    if strgfeat == 'timeshftplanther':
                        strg = '%s_phase_curve_atmospheric_thermal_shift_TESS' % gdat.liststrgcomp[j]
                    if strgfeat == 'timeshftplanrefl':
                        strg = '%s_phase_curve_atmospheric_reflected_shift_TESS' % gdat.liststrgcomp[j]
            
                if strg in gdat.objtalle[strgpdfn].posterior_params.keys():
                    gdat.dictlist[strgfeat][:, j] = gdat.objtalle[strgpdfn].posterior_params[strg][gdat.indxsamp]
                else:
                    gdat.dictlist[strgfeat][:, j] = np.zeros(gdat.numbsamp) + allesfitter.config.BASEMENT.params[strg]

    if gdat.typeverb > 0:
        print('Calculating derived variables...')
    # derived variables
    ## get samples from the star's variables

    # stellar features
    for featstar in gdat.listfeatstar:
        meantemp = getattr(gdat, featstar)
        stdvtemp = getattr(gdat, 'stdv' + featstar)
        
        # not a specific host star
        if meantemp is None:
            continue

        if not np.isfinite(meantemp):
            if gdat.typeverb > 0:
                print('Stellar feature %s is not finite!' % featstar)
                print('featstar')
                print(featstar)
                print('meantemp')
                print(meantemp)
                print('stdvtemp')
                print(stdvtemp)
            gdat.dictlist[featstar] = np.empty(gdat.numbsamp) + np.nan
        elif stdvtemp == 0.:
            gdat.dictlist[featstar] = meantemp + np.zeros(gdat.numbsamp)
        else:
            gdat.dictlist[featstar] = tdpy.samp_gaustrun(gdat.numbsamp, meantemp, stdvtemp, 0., np.inf)
        
        gdat.dictlist[featstar] = np.vstack([gdat.dictlist[featstar]] * gdat.numbcomp).T
    
    # inclination [degree]
    gdat.dictlist['incl'] = np.arccos(gdat.dictlist['cosicomp']) * 180. / np.pi
    
    # log g of the host star
    gdat.dictlist['loggstar'] = gdat.dictlist['massstar'] / gdat.dictlist['radistar']**2

    gdat.dictlist['ecce'] = gdat.dictlist['esin']**2 + gdat.dictlist['ecos']**2
    
    if gdat.boolmodlpsys:
        # radius of the planets
        gdat.dictlist['radicomp'] = gdat.dictfact['rsre'] * gdat.dictlist['radistar'] * gdat.dictlist['rratcomp'] # [R_E]
    
        # semi-major axis
        gdat.dictlist['smax'] = (gdat.dictlist['radicomp'] + gdat.dictlist['radistar']) / gdat.dictlist['rsmacomp']
    
        if strgpdfn == '0003' or strgpdfn == '0004':
            gdat.dictlist['amplnigh'] = gdat.dictlist['sbrtrati'] * gdat.dictlist['rratcomp']**2
        if strgpdfn == '0003':
            gdat.dictlist['phasshftplan'] = gdat.dictlist['timeshftplan'] * 360. / gdat.dictlist['pericomp']
        if strgpdfn == '0004':
            gdat.dictlist['phasshftplanther'] = gdat.dictlist['timeshftplanther'] * 360. / gdat.dictlist['pericomp']
            gdat.dictlist['phasshftplanrefl'] = gdat.dictlist['timeshftplanrefl'] * 360. / gdat.dictlist['pericomp']

        # planet equilibrium temperature
        gdat.dictlist['tmptplan'] = gdat.dictlist['tmptstar'] * np.sqrt(gdat.dictlist['radistar'] / 2. / gdat.dictlist['smax'])
        
        # stellar luminosity
        gdat.dictlist['lumistar'] = gdat.dictlist['radistar']**2 * (gdat.dictlist['tmptstar'] / 5778.)**4
        
        # insolation
        gdat.dictlist['inso'] = gdat.dictlist['lumistar'] / gdat.dictlist['smax']**2
    
        # predicted planet mass
        if gdat.typeverb > 0:
            print('Calculating predicted masses...')
        
        gdat.dictlist['masscomppred'] = np.full_like(gdat.dictlist['radicomp'], np.nan)
        gdat.dictlist['masscomppred'] = ephesus.retr_massfromradi(gdat.dictlist['radicomp'])
        gdat.dictlist['masscomppred'] = gdat.dictlist['masscomppred']
        
        # mass used for later calculations
        gdat.dictlist['masscompused'] = np.empty_like(gdat.dictlist['masscomppred'])
        
        # temp
        gdat.dictlist['masscomp'] = np.zeros_like(gdat.dictlist['esin'])
        gdat.dictlist['masscompused'] = gdat.dictlist['masscomppred']
        #for j in gmod.indxcomp:
        #    if 
        #        gdat.dictlist['masscompused'][:, j] = 
        #    else:
        #        gdat.dictlist['masscompused'][:, j] = 
    
        # density of the planet
        gdat.dictlist['densplan'] = gdat.dictlist['masscompused'] / gdat.dictlist['radicomp']**3

        # escape velocity
        gdat.dictlist['vesc'] = ephesus.retr_vesc(gdat.dictlist['masscompused'], gdat.dictlist['radicomp'])
        
        for j in gmod.indxcomp:
            strgratiperi = 'ratiperi_%s' % gdat.liststrgcomp[j]
            strgratiradi = 'ratiradi_%s' % gdat.liststrgcomp[j]
            for jj in gmod.indxcomp:
                gdat.dictlist[strgratiperi] = gdat.dictlist['pericomp'][:, j] / gdat.dictlist['pericomp'][:, jj]
                gdat.dictlist[strgratiradi] = gdat.dictlist['radicomp'][:, j] / gdat.dictlist['radicomp'][:, jj]
    
        gdat.dictlist['depttrancomp'] = 1e3 * gdat.dictlist['rratcomp']**2 # [ppt]
        # TSM
        gdat.dictlist['tsmm'] = ephesus.retr_tsmm(gdat.dictlist['radicomp'], gdat.dictlist['tmptplan'], \
                                                                                    gdat.dictlist['masscompused'], gdat.dictlist['radistar'], gdat.jmagsyst)
        
        # ESM
        gdat.dictlist['esmm'] = ephesus.retr_esmm(gdat.dictlist['tmptplan'], gdat.dictlist['tmptstar'], \
                                                                                    gdat.dictlist['radicomp'], gdat.dictlist['radistar'], gdat.kmagsyst)
        
    else:
        # semi-major axis
        gdat.dictlist['smax'] = (gdat.dictlist['radistar']) / gdat.dictlist['rsmacomp']
    
    # temp
    gdat.dictlist['sini'] = np.sqrt(1. - gdat.dictlist['cosicomp']**2)
    gdat.dictlist['omeg'] = 180. / np.pi * np.mod(np.arctan2(gdat.dictlist['esin'], gdat.dictlist['ecos']), 2 * np.pi)
    gdat.dictlist['rs2a'] = gdat.dictlist['rsmacomp'] / (1. + gdat.dictlist['rratcomp'])
    gdat.dictlist['sinw'] = np.sin(np.pi / 180. * gdat.dictlist['omeg'])
    gdat.dictlist['imfa'] = ephesus.retr_imfa(gdat.dictlist['cosicomp'], gdat.dictlist['rs2a'], gdat.dictlist['ecce'], gdat.dictlist['sinw'])
   
    # RV semi-amplitude
    gdat.dictlist['rvelsemapred'] = ephesus.retr_rvelsema(gdat.dictlist['pericomp'], gdat.dictlist['masscomppred'], \
                                                                        gdat.dictlist['massstar'], gdat.dictlist['incl'], gdat.dictlist['ecce'])
    
    ## expected Doppler beaming (DB)
    deptbeam = 1e3 * 4. * gdat.dictlist['rvelsemapred'] / 3e8 * gdat.consbeam # [ppt]

    ## expected ellipsoidal variation (EV)
    ## limb and gravity darkening coefficients from Claret2017
    if gdat.typeverb > 0:
        print('temp: connect these to Claret2017')
    # linear limb-darkening coefficient
    coeflidaline = 0.4
    # gravitational darkening coefficient
    coefgrda = 0.2
    alphelli = ephesus.retr_alphelli(coeflidaline, coefgrda)
    gdat.dictlist['deptelli'] = 1e3 * alphelli * gdat.dictlist['masscompused'] * np.sin(gdat.dictlist['incl'] / 180. * np.pi)**2 / \
                                                                  gdat.dictlist['massstar'] * (gdat.dictlist['radistar'] / gdat.dictlist['smax'])**3 # [ppt]
    if gdat.typeverb > 0:
        print('Calculating durations...')
                      
    gdat.dictlist['duratranfull'] = ephesus.retr_duratranfull(gdat.dictlist['pericomp'], gdat.dictlist['rsmacomp'], gdat.dictlist['cosicomp'], gdat.dictlist['rratcomp'])
    gdat.dictlist['duratrantotl'] = ephesus.retr_duratrantotl(gdat.dictlist['pericomp'], gdat.dictlist['rsmacomp'], gdat.dictlist['cosicomp'])
    
    gdat.dictlist['maxmdeptblen'] = 1e3 * (1. - gdat.dictlist['duratranfull'] / gdat.dictlist['duratrantotl'])**2 / \
                                                                    (1. + gdat.dictlist['duratranfull'] / gdat.dictlist['duratrantotl'])**2 # [ppt]
    gdat.dictlist['minmdilu'] = gdat.dictlist['depttrancomp'] / gdat.dictlist['maxmdeptblen']
    gdat.dictlist['minmratiflux'] = gdat.dictlist['minmdilu'] / (1. - gdat.dictlist['minmdilu'])
    gdat.dictlist['maxmdmag'] = -2.5 * np.log10(gdat.dictlist['minmratiflux'])
    
    # orbital
    ## RM effect
    gdat.dictlist['amplrmef'] = 2. / 3. * gdat.dictlist['vsiistar'] * 1e-3 * gdat.dictlist['depttrancomp'] * np.sqrt(1. - gdat.dictlist['imfa'])
    gdat.dictlist['stnormefpfss'] = (gdat.dictlist['amplrmef'] / 0.9) * np.sqrt(gdat.dictlist['duratranfull'] / (10. / 60. / 24.))
    
    # 0003 single component, offset
    # 0004 double component, offset
    if strgpdfn == '0003':
        frac = np.random.rand(gdat.dictlist['amplplan'].size).reshape(gdat.dictlist['amplplan'].shape)
        gdat.dictlist['amplplanther'] = gdat.dictlist['amplplan'] * frac
        gdat.dictlist['amplplanrefl'] = gdat.dictlist['amplplan'] * (1. - frac)
    
    if strgpdfn == '0004':
        # temp -- this does not work for two component (thermal + reflected)
        gdat.dictlist['amplseco'] = gdat.dictlist['amplnigh'] + gdat.dictlist['amplplanther'] + gdat.dictlist['amplplanrefl']
    if strgpdfn == '0003':
        # temp -- this does not work when phase shift is nonzero
        gdat.dictlist['amplseco'] = gdat.dictlist['amplnigh'] + gdat.dictlist['amplplan']
    
    if strgpdfn == '0003' or strgpdfn == '0004':
        gdat.dictlist['albg'] = retr_albg(gdat.dictlist['amplplanrefl'], gdat.dictlist['radicomp'], gdat.dictlist['smax'])

    if gdat.typeverb > 0:
        print('Calculating the equilibrium temperature of the planets...')
    
    gdat.dictlist['tmptequi'] = gdat.dictlist['tmptstar'] * np.sqrt(gdat.dictlist['radistar'] / gdat.dictlist['smax'] / 2.)
    
    if False and gdat.labltarg == 'WASP-121' and strgpdfn != 'prio':
        
        # read and parse ATMO posterior
        ## get secondary depth data from Tom
        path = gdat.pathdatatarg + 'ascii_output/EmissionDataArray.txt'
        print('Reading from %s...' % path)
        arrydata = np.loadtxt(path)
        print('arrydata')
        summgene(arrydata)
        print('arrydata[0, :]')
        print(arrydata[0, :])
        path = gdat.pathdatatarg + 'ascii_output/EmissionModelArray.txt'
        print('Reading from %s...' % path)
        arrymodl = np.loadtxt(path)
        print('arrymodl')
        summgene(arrymodl)
        print('Secondary eclipse depth mean and standard deviation:')
        # get wavelengths
        path = gdat.pathdatatarg + 'ascii_output/ContribFuncWav.txt'
        print('Reading from %s...' % path)
        wlen = np.loadtxt(path)
        path = gdat.pathdatatarg + 'ascii_output/ContribFuncWav.txt'
        print('Reading from %s...' % path)
        wlenctrb = np.loadtxt(path, skiprows=1)
   
        ### spectrum of the host star
        gdat.meanwlenthomraww = arrymodl[:, 0]
        gdat.specstarthomraww = arrymodl[:, 9]
        
        ## calculate the geometric albedo "informed" by the ATMO posterior
        wlenmodl = arrymodl[:, 0]
        deptmodl = arrymodl[:, 1]
        indxwlenmodltess = np.where((wlenmodl > 0.6) & (wlenmodl < 0.95))[0]
        gdat.amplplantheratmo = np.mean(deptmodl[indxwlenmodltess])
        gdat.dictlist['amplplanreflatmo'] = 1e-6 * arrydata[0, 2] + np.random.randn(gdat.numbsamp).reshape((gdat.numbsamp, 1)) \
                                                                                                    * arrydata[0, 3] * 1e-6 - gdat.amplplantheratmo
        #gdat.dictlist['amplplanreflatmo'] = gdat.dictlist['amplplan'] - gdat.amplplantheratmo
        gdat.dictlist['albginfo'] = retr_albg(gdat.dictlist['amplplanreflatmo'], gdat.dictlist['radicomp'], gdat.dictlist['smax'])
        
        ## update Tom's secondary (dayside) with the posterior secondary depth, since Tom's secondary was preliminary (i.e., 490+-50 ppm)
        print('Updating the multiband depth array with dayside and adding the nightside...')
        medideptseco = np.median(gdat.dictlist['amplseco'][:, 0])
        stdvdeptseco = (np.percentile(gdat.dictlist['amplseco'][:, 0], 84.) - np.percentile(gdat.dictlist['amplseco'][:, 0], 16.)) / 2.
        arrydata[0, 2] = medideptseco * 1e3 # [ppm]
        arrydata[0, 3] = stdvdeptseco * 1e3 # [ppm]
        
        ## add the nightside depth
        medideptnigh = np.median(gdat.dictlist['amplnigh'][:, 0])
        stdvdeptnigh = (np.percentile(gdat.dictlist['amplnigh'][:, 0], 84.) - np.percentile(gdat.dictlist['amplnigh'][:, 0], 16.)) / 2.
        arrydata = np.concatenate((arrydata, np.array([[arrydata[0, 0], arrydata[0, 1], medideptnigh * 1e3, stdvdeptnigh * 1e6, 0, 0, 0, 0]])), axis=0) # [ppm]
        
        # calculate brightness temperatures
        gdat.listlablpara = [['Temperature', 'K']]
        gdat.rratmedi = np.median(gdat.dictlist['rratcomp'], axis=0)
        listscalpara = ['self']
        gdat.listminmpara = np.array([1000.])
        gdat.listmaxmpara = np.array([4000.])
        meangauspara = None
        stdvgauspara = None
        numbpara = len(gdat.listlablpara)
        numbsampwalk = 1000
        numbsampburnwalk = 5
        gdat.numbdatatmpt = arrydata.shape[0]
        gdat.indxdatatmpt = np.arange(gdat.numbdatatmpt)
        listtmpt = []
        specarry = np.empty((2, 3, gdat.numbdatatmpt))
        for k in gdat.indxdatatmpt:
            
            if not (k == 0 or k == gdat.numbdatatmpt - 1):
                continue
            gdat.minmwlen = arrydata[k, 0] - arrydata[k, 1]
            gdat.maxmwlen = arrydata[k, 0] + arrydata[k, 1]
            gdat.binswlen = np.linspace(gdat.minmwlen, gdat.maxmwlen, 100)
            gdat.meanwlen = (gdat.binswlen[1:] + gdat.binswlen[:-1]) / 2.
            gdat.diffwlen = (gdat.binswlen[1:] - gdat.binswlen[:-1]) / 2.
            gdat.cntrwlen = np.mean(gdat.meanwlen)
            strgextn = 'tmpt_%d' % k
            gdat.indxenerdata = k

            gdat.specstarintg = retr_modl_spec(gdat, gdat.tmptstar, strgtype='intg')
            
            gdat.specstarthomlogt = scipy.interpolate.interp1d(gdat.meanwlenthomraww, gdat.specstarthomraww)(gdat.cntrwlen)
            gdat.specstarthomdiff = gdat.specstarthomlogt / gdat.cntrwlen
            gdat.specstarthomintg = np.sum(gdat.diffwlen * \
                                    scipy.interpolate.interp1d(gdat.meanwlenthomraww, gdat.specstarthomraww)(gdat.meanwlen) / gdat.meanwlen)

            gdat.deptobsd = arrydata[k, 2]
            gdat.stdvdeptobsd = arrydata[k, 3]
            gdat.varideptobsd = gdat.stdvdeptobsd**2
            listtmpttemp = tdpy.samp(gdat, gdat.pathalle[strgpdfn], numbsampwalk, \
                                          retr_llik_spec, \
                                          gdat.listlablpara, listscalpara, gdat.listminmpara, gdat.listmaxmpara, meangauspara, stdvgauspara, numbdata, strgextn=strgextn, \
                                          pathbase=gdat.pathtargruns, \
                                          typeverb=gdat.typeverb, \
                                          numbsampburnwalk=numbsampburnwalk, boolplot=gdat.boolplot, \
                             )
            listtmpt.append(listtmpttemp)
        listtmpt = np.vstack(listtmpt).T
        indxsamp = np.random.choice(np.arange(listtmpt.shape[0]), size=gdat.numbsamp, replace=False)
        # dayside and nightside temperatures to be used for albedo and circulation efficiency calculation
        gdat.dictlist['tmptdayy'] = listtmpt[indxsamp, 0, None]
        gdat.dictlist['tmptnigh'] = listtmpt[indxsamp, -1, None]
        # dayside/nightside temperature contrast
        gdat.dictlist['tmptcont'] = (gdat.dictlist['tmptdayy'] - gdat.dictlist['tmptnigh']) / gdat.dictlist['tmptdayy']
        
    # copy the prior
    gdat.dictlist['projoblq'] = np.random.randn(gdat.numbsamp)[:, None] * gdat.stdvprojoblqprio[None, :] + gdat.projoblqprio[None, :]
    
    gdat.boolsampbadd = np.zeros(gdat.numbsamp, dtype=bool)
    for j in gmod.indxcomp:
        boolsampbaddtemp = ~np.isfinite(gdat.dictlist['maxmdmag'][:, j])
        gdat.boolsampbadd = gdat.boolsampbadd | boolsampbaddtemp
    gdat.indxsampbadd = np.where(gdat.boolsampbadd)[0]
    gdat.indxsamptran = np.setdiff1d(gdat.indxsamp, gdat.indxsampbadd)

    gdat.liststrgfeat = np.array(list(gdat.dictlist.keys()))
    for strgfeat in gdat.liststrgfeat:
        errrshap = list(gdat.dictlist[strgfeat].shape)
        errrshap[0] = 3
        gdat.dictpost[strgfeat] = np.empty(errrshap)
        gdat.dicterrr[strgfeat] = np.empty(errrshap)
        
        # transit duration can be NaN when not transiting
        gdat.dictpost[strgfeat][0, ...] = np.nanpercentile(gdat.dictlist[strgfeat], 16., 0)
        gdat.dictpost[strgfeat][1, ...] = np.nanpercentile(gdat.dictlist[strgfeat], 50., 0)
        gdat.dictpost[strgfeat][2, ...] = np.nanpercentile(gdat.dictlist[strgfeat], 84., 0)
        gdat.dicterrr[strgfeat][0, ...] = gdat.dictpost[strgfeat][1, ...]
        gdat.dicterrr[strgfeat][1, ...] = gdat.dictpost[strgfeat][1, ...] - gdat.dictpost[strgfeat][0, ...]
        gdat.dicterrr[strgfeat][2, ...] = gdat.dictpost[strgfeat][2, ...] - gdat.dictpost[strgfeat][1, ...]
        
    # augment
    gdat.dictfeatobjt['radistar'] = gdat.dicterrr['radistar'][0, :]
    gdat.dictfeatobjt['radicomp'] = gdat.dicterrr['radicomp'][0, :]
    gdat.dictfeatobjt['masscomp'] = gdat.dicterrr['masscomp'][0, :]
    gdat.dictfeatobjt['stdvradistar'] = np.mean(gdat.dicterrr['radistar'][1:, :], 0)
    gdat.dictfeatobjt['stdvmassstar'] = np.mean(gdat.dicterrr['massstar'][1:, :], 0)
    gdat.dictfeatobjt['stdvtmptstar'] = np.mean(gdat.dicterrr['tmptstar'][1:, :], 0)
    gdat.dictfeatobjt['stdvloggstar'] = np.mean(gdat.dicterrr['loggstar'][1:, :], 0)
    gdat.dictfeatobjt['stdvradicomp'] = np.mean(gdat.dicterrr['radicomp'][1:, :], 0)
    gdat.dictfeatobjt['stdvmasscomp'] = np.mean(gdat.dicterrr['masscomp'][1:, :], 0)
    gdat.dictfeatobjt['stdvtmptplan'] = np.mean(gdat.dicterrr['tmptplan'][1:, :], 0)
    gdat.dictfeatobjt['stdvesmm'] = np.mean(gdat.dicterrr['esmm'][1:, :], 0)
    gdat.dictfeatobjt['stdvtsmm'] = np.mean(gdat.dicterrr['tsmm'][1:, :], 0)
    

def proc_alle(gdat, typemodl):
    
    #_0003: single component offset baseline
    #_0004: multiple components, offset baseline
        
    if gdat.typeverb > 0:
        print('Processing allesfitter model %s...' % typemodl)
    # allesfit run folder
    gdat.pathalle[typemodl] = gdat.pathallebase + 'allesfit_%s/' % typemodl
    
    # make sure the folder exists
    cmnd = 'mkdir -p %s' % gdat.pathalle[typemodl]
    os.system(cmnd)
    
    # write the input data file
    for b in gdat.indxdatatser:
        for p in gdat.indxinst[b]:
            path = gdat.pathalle[typemodl] + gdat.liststrginst[b][p] + '.csv'
            if not os.path.exists(path):
            
                if gdat.boolinfefoldbind:
                    listarrytserbdtrtemp = np.copy(gdat.arrypcur['primbdtrbindtotl'][b][p][0])
                    listarrytserbdtrtemp[:, 0] *= gdat.pericompprio[0]
                    listarrytserbdtrtemp[:, 0] += gdat.epocmtracompprio[0]
                else:
                    listarrytserbdtrtemp = gdat.arrytser['bdtr'][b][p]
                
                # make sure the data are time-sorted
                #indx = np.argsort(listarrytserbdtrtemp[:, 0])
                #listarrytserbdtrtemp = listarrytserbdtrtemp[indx, :]
                    
                if gdat.typeverb > 0:
                    print('Writing to %s...' % path)
                np.savetxt(path, listarrytserbdtrtemp, delimiter=',', header='time,%s,%s_err' % (gdat.liststrgtseralle[b], gdat.liststrgtseralle[b]))
    
    ## params_star
    pathparastar = gdat.pathalle[typemodl] + 'params_star.csv'
    if not os.path.exists(pathparastar):
        objtfile = open(pathparastar, 'w')
        objtfile.write('#R_star,R_star_lerr,R_star_uerr,M_star,M_star_lerr,M_star_uerr,Teff_star,Teff_star_lerr,Teff_star_uerr\n')
        objtfile.write('#R_sun,R_sun,R_sun,M_sun,M_sun,M_sun,K,K,K\n')
        objtfile.write('%g,%g,%g,%g,%g,%g,%g,%g,%g' % (gdat.radistar, gdat.stdvradistar, gdat.stdvradistar, \
                                                       gdat.massstar, gdat.stdvmassstar, gdat.stdvmassstar, \
                                                                                                      gdat.tmptstar, gdat.stdvtmptstar, gdat.stdvtmptstar))
        if gdat.typeverb > 0:
            print('Writing to %s...' % pathparastar)
        objtfile.close()

    ## params
    dictalleparadefa = dict()
    pathpara = gdat.pathalle[typemodl] + 'params.csv'
    if not os.path.exists(pathpara):
        cmnd = 'touch %s' % (pathpara)
        print(cmnd)
        os.system(cmnd)
    
        for j in gmod.indxcomp:
            strgrrat = '%s_rr' % gdat.liststrgcomp[j]
            strgrsma = '%s_rsuma' % gdat.liststrgcomp[j]
            strgcosi = '%s_cosi' % gdat.liststrgcomp[j]
            strgepoc = '%s_epoch' % gdat.liststrgcomp[j]
            strgperi = '%s_period' % gdat.liststrgcomp[j]
            strgecos = '%s_f_c' % gdat.liststrgcomp[j]
            strgesin = '%s_f_s' % gdat.liststrgcomp[j]
            strgrvelsema = '%s_K' % gdat.liststrgcomp[j]
            dictalleparadefa[strgrrat] = ['%f' % gdat.rratcompprio[j], '1', 'uniform 0 %f' % (4 * gdat.rratcompprio[j]), \
                                                                            '$R_{%s} / R_\star$' % gdat.liststrgcomp[j], '']
            
            dictalleparadefa[strgrsma] = ['%f' % gdat.rsmacompprio[j], '1', 'uniform 0 %f' % (4 * gdat.rsmacompprio[j]), \
                                                                      '$(R_\star + R_{%s}) / a_{%s}$' % (gdat.liststrgcomp[j], gdat.liststrgcomp[j]), '']
            dictalleparadefa[strgcosi] = ['%f' % gdat.cosicompprio[j], '1', 'uniform 0 %f' % max(0.1, 4 * gdat.cosicompprio[j]), \
                                                                                        '$\cos{i_{%s}}$' % gdat.liststrgcomp[j], '']
            dictalleparadefa[strgepoc] = ['%f' % gdat.epocmtracompprio[j], '1', \
                                            'uniform %f %f' % (gdat.epocmtracompprio[j] - gdat.stdvepocmtracompprio[j], gdat.epocmtracompprio[j] + gdat.stdvepocmtracompprio[j]), \
                                                                    '$T_{0;%s}$' % gdat.liststrgcomp[j], '$\mathrm{BJD}$']
            dictalleparadefa[strgperi] = ['%f' % gdat.pericompprio[j], '1', \
                                     'uniform %f %f' % (gdat.pericompprio[j] - 3. * gdat.stdvpericompprio[j], gdat.pericompprio[j] + 3. * gdat.stdvpericompprio[j]), \
                                                                    '$P_{%s}$' % gdat.liststrgcomp[j], 'days']
            dictalleparadefa[strgecos] = ['%f' % gdat.ecoscompprio[j], '0', 'uniform -0.9 0.9', \
                                                                '$\sqrt{e_{%s}} \cos{\omega_{%s}}$' % (gdat.liststrgcomp[j], gdat.liststrgcomp[j]), '']
            dictalleparadefa[strgesin] = ['%f' % gdat.esincompprio[j], '0', 'uniform -0.9 0.9', \
                                                                '$\sqrt{e_{%s}} \sin{\omega_{%s}}$' % (gdat.liststrgcomp[j], gdat.liststrgcomp[j]), '']
            dictalleparadefa[strgrvelsema] = ['%f' % gdat.rvelsemaprio[j], '0', \
                                    'uniform %f %f' % (max(0, gdat.rvelsemaprio[j] - 5 * gdat.stdvrvelsemaprio[j]), gdat.rvelsemaprio[j] + 5 * gdat.stdvrvelsemaprio[j]), \
                                                                '$K_{%s}$' % gdat.liststrgcomp[j], '']
            if typemodl == '0003' or typemodl == '0004':
                for b in gdat.indxdatatser:
                    if b != 0:
                        continue
                    for p in gdat.indxinst[b]:
                        strgsbrt = '%s_sbratio_' % gdat.liststrgcomp[j] + gdat.liststrginst[b][p]
                        dictalleparadefa[strgsbrt] = ['1e-3', '1', 'uniform 0 1', '$J_{%s; \mathrm{%s}}$' % \
                                                                            (gdat.liststrgcomp[j], gdat.listlablinst[b][p]), '']
                        
                        dictalleparadefa['%s_phase_curve_beaming_%s' % (gdat.liststrgcomp[j], gdat.liststrginst[b][p])] = \
                                             ['0', '1', 'uniform 0 10', '$A_\mathrm{beam; %s; %s}$' % (gdat.liststrgcomp[j], gdat.listlablinst[b][p]), '']
                        dictalleparadefa['%s_phase_curve_atmospheric_%s' % (gdat.liststrgcomp[j], gdat.liststrginst[b][p])] = \
                                             ['0', '1', 'uniform 0 10', '$A_\mathrm{atmo; %s; %s}$' % (gdat.liststrgcomp[j], gdat.listlablinst[b][p]), '']
                        dictalleparadefa['%s_phase_curve_ellipsoidal_%s' % (gdat.liststrgcomp[j], gdat.liststrginst[b][p])] = \
                                             ['0', '1', 'uniform 0 10', '$A_\mathrm{elli; %s; %s}$' % (gdat.liststrgcomp[j], gdat.listlablinst[b][p]), '']

            if typemodl == '0003':
                for b in gdat.indxdatatser:
                    if b != 0:
                        continue
                    for p in gdat.indxinst[b]:
                        maxmshft = 0.25 * gdat.pericompprio[j]
                        minmshft = -maxmshft

                        dictalleparadefa['%s_phase_curve_atmospheric_shift_%s' % (gdat.liststrgcomp[j], gdat.liststrginst[b][p])] = \
                                         ['0', '1', 'uniform %.3g %.3g' % (minmshft, maxmshft), \
                                            '$\Delta_\mathrm{%s; %s}$' % (gdat.liststrgcomp[j], gdat.listlablinst[b][p]), '']
        if typemodl == 'pfss':
            for p in gdat.indxinst[1]:
                                ['', 'host_vsini,%g,1,uniform %g %g,$v \sin i$$,\n' % (gdat.vsiistar, 0, \
                                                                                                                            10 * gdat.vsiistar)], \
                                ['', 'host_lambda_%s,%g,1,uniform %g %g,$v \sin i$$,\n' % (gdat.liststrginst[1][p], gdat.lambstarprio, 0, \
                                                                                                                            10 * gdat.lambstarprio)], \
        
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                strgldc1 = 'host_ldc_q1_%s' % gdat.liststrginst[b][p]
                strgldc2 = 'host_ldc_q2_%s' % gdat.liststrginst[b][p]
                strgscal = 'ln_err_flux_%s' % gdat.liststrginst[b][p]
                strgbaseoffs = 'baseline_offset_flux_%s' % gdat.liststrginst[b][p]
                strggprosigm = 'baseline_gp_matern32_lnsigma_flux_%s' % gdat.liststrginst[b][p]
                strggprorhoo = 'baseline_gp_matern32_lnrho_flux_%s' % gdat.liststrginst[b][p]
                dictalleparadefa[strgldc1] = ['0.5', '1', 'uniform 0 1', '$q_{1; \mathrm{%s}}$' % gdat.listlablinst[b][p], '']
                dictalleparadefa[strgldc2] = ['0.5', '1', 'uniform 0 1', '$q_{2; \mathrm{%s}}$' % gdat.listlablinst[b][p], '']
                dictalleparadefa[strgscal] = ['-7', '1', 'uniform -10 -4', '$\ln{\sigma_\mathrm{%s}}$' % gdat.listlablinst[b][p], '']
                dictalleparadefa[strgbaseoffs] = ['0', '1', 'uniform -1 1', '$O_{\mathrm{%s}}$' % gdat.listlablinst[b][p], '']
                if b == 1:
                    dictalleparadefa['ln_jitter_rv_%s' % gdat.liststrginst[b][p]] = ['-10', '1', 'uniform -20 20', \
                                                                            '$\ln{\sigma_{\mathrm{RV;%s}}}$' % gdat.listlablinst[b][p], '']
                #lineadde.extend([ \
                #            ['', '%s,%f,1,uniform %f %f,$\ln{\sigma_{GP;\mathrm{TESS}}}$,\n' % \
                #                 (strggprosigm, -6, -12, 12)], \
                #            ['', '%s,%f,1,uniform %f %f,$\ln{\\rho_{GP;\mathrm{TESS}}}$,\n' % \
                #                 (strggprorhoo, -2, -12, 12)], \
                #           ])
                
        writ_filealle(gdat, 'params.csv', gdat.pathalle[typemodl], gdat.dictdictallepara[typemodl], dictalleparadefa)
    
    ## settings
    dictallesettdefa = dict()
    if typemodl == 'pfss':
        for j in gmod.indxcomp:
            dictallesettdefa['%s_flux_weighted_PFS' % gdat.liststrgcomp[j]] = 'True'
    
    pathsett = gdat.pathalle[typemodl] + 'settings.csv'
    if not os.path.exists(pathsett):
        cmnd = 'touch %s' % (pathsett)
        print(cmnd)
        os.system(cmnd)
        
        dictallesettdefa['fast_fit_width'] = '%.3g' % np.amax(gdat.duramask) / 24.
        dictallesettdefa['multiprocess'] = 'True'
        dictallesettdefa['multiprocess_cores'] = 'all'

        dictallesettdefa['mcmc_nwalkers'] = '100'
        dictallesettdefa['mcmc_total_steps'] = '100'
        dictallesettdefa['mcmc_burn_steps'] = '10'
        dictallesettdefa['mcmc_thin_by'] = '5'
        
        for p in gdat.indxinst[0]:
            dictallesettdefa['inst_phot'] = '%s' % gdat.liststrginst[0][p]
        
        for b in gdat.indxdatatser:
            if b == 0:
                strg = 'phot'
            if b == 1:
                strg = 'rv'
            for p in gdat.indxinst[b]:
                dictallesettdefa['inst_%s' % strg] = '%s' % gdat.liststrginst[b][p]
                dictallesettdefa['host_ld_law_%s' % gdat.liststrginst[b][p]] = 'quad'
                dictallesettdefa['host_grid_%s' % gdat.liststrginst[b][p]] = 'very_sparse'
                dictallesettdefa['baseline_flux_%s' % gdat.liststrginst[b][p]] = 'sample_offset'
        
        #dictallesettdefa['use_host_density_prior'] = 'False'
        
        if typemodl == '0003' or typemodl == '0004':
            dictallesettdefa['phase_curve'] = 'True'
            dictallesettdefa['phase_curve_style'] = 'sine_physical'
        
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                for j in gmod.indxcomp:
                    dictallesettdefa['%s_grid_%s' % (gdat.liststrgcomp[j], gdat.liststrginst[b][p])] = 'very_sparse'
            
            if gdat.numbinst[b] > 0:
                if b == 0:
                    strg = 'companions_phot'
                if b == 1:
                    strg = 'companions_rv'
                varb = ''
                cntr = 0
                for j in gmod.indxcomp:
                    if cntr != 0:
                        varb += ' '
                    varb += '%s' % gdat.liststrgcomp[j]
                    cntr += 1
                dictallesettdefa[strg] = varb
        
        dictallesettdefa['fast_fit'] = 'True'

        writ_filealle(gdat, 'settings.csv', gdat.pathalle[typemodl], gdat.dictdictallesett[typemodl], dictallesettdefa)
    
    ## initial plot
    path = gdat.pathalle[typemodl] + 'results/initial_guess_b.pdf'
    if not os.path.exists(path):
        allesfitter.show_initial_guess(gdat.pathalle[typemodl])
    
    ## do the run
    path = gdat.pathalle[typemodl] + 'results/mcmc_save.h5'
    if not os.path.exists(path):
        allesfitter.mcmc_fit(gdat.pathalle[typemodl])
    else:
        print('%s exists... Skipping the orbit run.' % path)

    ## make the final plots
    path = gdat.pathalle[typemodl] + 'results/mcmc_corner.pdf'
    if not os.path.exists(path):
        allesfitter.mcmc_output(gdat.pathalle[typemodl])
        
    # read the allesfitter posterior
    if gdat.typeverb > 0:
        print('Reading from %s...' % gdat.pathalle[typemodl])
    gdat.objtalle[typemodl] = allesfitter.allesclass(gdat.pathalle[typemodl])
    
    gdat.numbsampalle = allesfitter.config.BASEMENT.settings['mcmc_total_steps']
    gdat.numbwalkalle = allesfitter.config.BASEMENT.settings['mcmc_nwalkers']
    gdat.numbsampalleburn = allesfitter.config.BASEMENT.settings['mcmc_burn_steps']
    gdat.numbsampallethin = allesfitter.config.BASEMENT.settings['mcmc_thin_by']

    print('gdat.numbwalkalle')
    print(gdat.numbwalkalle)
    print('gdat.numbsampalle')
    print(gdat.numbsampalle)
    print('gdat.numbsampalleburn')
    print(gdat.numbsampalleburn)
    print('gdat.numbsampallethin')
    print(gdat.numbsampallethin)

    gdat.numbsamp = gdat.objtalle[typemodl].posterior_params[list(gdat.objtalle[typemodl].posterior_params.keys())[0]].size
    
    print('gdat.numbsamp')
    print(gdat.numbsamp)

    # temp 
    if gdat.numbsamp > 10000:
        gdat.indxsamp = np.random.choice(np.arange(gdat.numbsamp), size=10000, replace=False)
        gdat.numbsamp = 10000
    else:
        gdat.indxsamp = np.arange(gdat.numbsamp)
    
    print('gdat.numbsamp')
    print(gdat.numbsamp)
    
    calc_feat(gdat, typemodl)

    gdat.arrytser['bdtr'+typemodl] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.arrytser['modl'+typemodl] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.arrytser['resi'+typemodl] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.listarrytser['bdtr'+typemodl] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.listarrytser['modl'+typemodl] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.listarrytser['resi'+typemodl] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    
    for b in gdat.indxdatatser:
        for p in gdat.indxinst[b]:
            gdat.arrytser['modl'+typemodl][b][p] = np.empty((gdat.time[b][p].size, 3))
            gdat.arrytser['modl'+typemodl][b][p][:, 0] = gdat.time[b][p]
            gdat.arrytser['modl'+typemodl][b][p][:, 1] = gdat.objtalle[typemodl].get_posterior_median_model(gdat.liststrginst[b][p], \
                                                                                                             gdat.liststrgtseralle[b], xx=gdat.time[b][p])
            gdat.arrytser['modl'+typemodl][b][p][:, 2] = 0.

            gdat.arrytser['resi'+typemodl][b][p] = np.copy(gdat.arrytser['bdtr'][b][p])
            gdat.arrytser['resi'+typemodl][b][p][:, 1] -= gdat.arrytser['modl'+typemodl][b][p][:, 1]
            for y in gdat.indxchun[b][p]:
                gdat.listarrytser['modl'+typemodl][b][p][y] = np.copy(gdat.listarrytser['bdtr'][b][p][y])
                gdat.listarrytser['modl'+typemodl][b][p][y][:, 1] = gdat.objtalle[typemodl].get_posterior_median_model(gdat.liststrginst[b][p], \
                                                                                                       gdat.liststrgtseralle[b], xx=gdat.listtime[b][p][y])
                
                gdat.listarrytser['resi'+typemodl][b][p][y] = np.copy(gdat.listarrytser['bdtr'][b][p][y])
                gdat.listarrytser['resi'+typemodl][b][p][y][:, 1] -= gdat.listarrytser['modl'+typemodl][b][p][y][:, 1]
    
                # plot residuals
                if gdat.boolplottser:
                    plot_tser(gdat, b, p, y, 'resi' + typemodl)

    # write the model to file
    for b in gdat.indxdatatser:
        for p in gdat.indxinst[b]:
            path = gdat.pathdatatarg + 'arry%smodl_%s.csv' % (gdat.liststrgdatatser[b], gdat.liststrginst[b][p])
            if not os.path.exists(path):
                if gdat.typeverb > 0:
                    print('Writing to %s...' % path)
                np.savetxt(path, gdat.arrytser['modl'+typemodl][b][p], delimiter=',', \
                                                        header='time,%s,%s_err' % (gdat.liststrgtseralle[b], gdat.liststrgtseralle[b]))

    # number of samples to plot
    gdat.arrypcur['primbdtr'+typemodl] = [[[[] for j in gmod.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.arrypcur['primbdtr'+typemodl+'bindtotl'] = [[[[] for j in gmod.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.arrypcur['primbdtr'+typemodl+'bindzoom'] = [[[[] for j in gmod.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    
    gdat.listarrypcur = dict()
    gdat.listarrypcur['quadmodl'+typemodl] = [[[[] for j in gmod.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    for b in gdat.indxdatatser:
        for p in gdat.indxinst[b]:
            for j in gmod.indxcomp:
                gdat.listarrypcur['quadmodl'+typemodl][b][p][j] = np.empty((gdat.numbsampplot, gdat.numbtimeclen[b][p][j], 3))
    
    gdat.arrypcur['primbdtr'+typemodl] = [[[[] for j in gmod.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.arrypcur['primmodltotl'+typemodl] = [[[[] for j in gmod.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.arrytser['modlbase'+typemodl] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    gdat.listarrytser['modlbase'+typemodl] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    
    gdat.listarrytsermodl = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    for b in gdat.indxdatatser:
        for p in gdat.indxinst[b]:
            gdat.listarrytsermodl[b][p] = np.empty((gdat.numbsampplot, gdat.numbtime[b][p], 3))
       
    for strgpcur in gdat.liststrgpcur:
        gdat.arrytser[strgpcur+typemodl] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                gdat.arrytser[strgpcur+typemodl][b][p] = np.copy(gdat.arrytser['bdtr'][b][p])
    for strgpcurcomp in gdat.liststrgpcurcomp:
        gdat.arrytser[strgpcurcomp+typemodl] = [[[[] for j in gmod.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                for j in gmod.indxcomp:
                    gdat.arrytser[strgpcurcomp+typemodl][b][p][j] = np.copy(gdat.arrytser['bdtr'][b][p])
    for strgpcurcomp in gdat.liststrgpcurcomp + gdat.liststrgpcur:
        for strgextnbins in ['', 'bindtotl']:
            gdat.arrypcur['quad' + strgpcurcomp + typemodl + strgextnbins] = [[[[] for j in gmod.indxcomp] \
                                                                                    for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
    
    for b in gdat.indxdatatser:
        for p in gdat.indxinst[b]:
        
            gdat.listlcurmodl = np.empty((gdat.numbsampplot, gdat.time[b][p].size))
            print('Phase-folding the posterior samples from the model light curve...')
            for ii in tqdm(range(gdat.numbsampplot)):
                i = gdat.indxsampplot[ii]
                
                # this is only the physical model and excludes the baseline, which is available separately via get_one_posterior_baseline()
                gdat.listarrytsermodl[b][p][ii, :, 1] = gdat.objtalle[typemodl].get_one_posterior_model(gdat.liststrginst[b][p], \
                                                                        gdat.liststrgtseralle[b], xx=gdat.time[b][p], sample_id=i)
                
                for j in gmod.indxcomp:
                    gdat.listarrypcur['quadmodl'+typemodl][b][p][j][ii, :, :] = \
                                            ephesus.fold_tser(gdat.listarrytsermodl[b][p][ii, gdat.listindxtimeclen[j][b][p], :], \
                                                                                   gdat.dicterrr['epocmtracomp'][0, j], gdat.dicterrr['pericomp'][0, j], phasshft=0.25)

            
            ## plot components in the zoomed panel
            for j in gmod.indxcomp:
                
                gdat.objtalle[typemodl] = allesfitter.allesclass(gdat.pathalle[typemodl])
                ### total model for this planet
                gdat.arrytser['modltotl'+typemodl][b][p][j][:, 1] = gdat.objtalle[typemodl].get_posterior_median_model(gdat.liststrginst[b][p], \
                                                                                                                                'flux', xx=gdat.time[b][p])
                
                ### stellar baseline
                gdat.objtalle[typemodl] = allesfitter.allesclass(gdat.pathalle[typemodl])
                gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_beaming_TESS'] = 0
                gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_ellipsoidal_TESS'] = 0
                if typemodl == '0003':
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_TESS'] = 0
                if typemodl == '0004':
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_thermal_TESS'] = 0
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_reflected_TESS'] = 0
                gdat.objtalle[typemodl].posterior_params_median['b_sbratio_TESS'] = 0
                gdat.arrytser['modlstel'+typemodl][b][p][j][:, 1] = gdat.objtalle[typemodl].get_posterior_median_model(gdat.liststrginst[b][p], \
                                                                                                                                'flux', xx=gdat.time[b][p])
                
                ### EV
                gdat.objtalle[typemodl] = allesfitter.allesclass(gdat.pathalle[typemodl])
                gdat.objtalle[typemodl].posterior_params_median['b_sbratio_TESS'] = 0
                gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_beaming_TESS'] = 0
                if typemodl == '0003':
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_TESS'] = 0
                if typemodl == '0004':
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_thermal_TESS'] = 0
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_reflected_TESS'] = 0
                gdat.arrytser['modlelli'+typemodl][b][p][j][:, 1] = gdat.objtalle[typemodl].get_posterior_median_model(gdat.liststrginst[b][p], \
                                                                                                                            'flux', xx=gdat.time[b][p])
                gdat.arrytser['modlelli'+typemodl][b][p][j][:, 1] -= gdat.arrytser['modlstel'+typemodl][b][p][j][:, 1]
                
                ### beaming
                gdat.objtalle[typemodl] = allesfitter.allesclass(gdat.pathalle[typemodl])
                gdat.objtalle[typemodl].posterior_params_median['b_sbratio_TESS'] = 0
                gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_ellipsoidal_TESS'] = 0
                if typemodl == '0003':
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_TESS'] = 0
                if typemodl == '0004':
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_thermal_TESS'] = 0
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_reflected_TESS'] = 0
                gdat.arrytser['modlbeam'+typemodl][b][p][j][:, 1] = gdat.objtalle[typemodl].get_posterior_median_model(gdat.liststrginst[b][p], \
                                                                                                                            'flux', xx=gdat.time[b][p])
                gdat.arrytser['modlbeam'+typemodl][b][p][j][:, 1] -= gdat.arrytser['modlstel'+typemodl][b][p][j][:, 1]
                
                # planetary
                gdat.arrytser['modlplan'+typemodl][b][p][j][:, 1] = gdat.arrytser['modltotl'+typemodl][b][p][j][:, 1] \
                                                                      - gdat.arrytser['modlstel'+typemodl][b][p][j][:, 1] \
                                                                      - gdat.arrytser['modlelli'+typemodl][b][p][j][:, 1] \
                                                                      - gdat.arrytser['modlbeam'+typemodl][b][p][j][:, 1]
                
                offsdays = np.mean(gdat.arrytser['modlplan'+typemodl][b][p][j][gdat.listindxtimetran[j][b][p][1], 1])
                gdat.arrytser['modlplan'+typemodl][b][p][j][:, 1] -= offsdays

                # planetary nightside
                gdat.objtalle[typemodl] = allesfitter.allesclass(gdat.pathalle[typemodl])
                gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_beaming_TESS'] = 0
                gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_ellipsoidal_TESS'] = 0
                if typemodl == '0003':
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_TESS'] = 0
                else:
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_thermal_TESS'] = 0
                    gdat.objtalle[typemodl].posterior_params_median['b_phase_curve_atmospheric_reflected_TESS'] = 0
                gdat.arrytser['modlnigh'+typemodl][b][p][j][:, 1] = gdat.objtalle[typemodl].get_posterior_median_model(gdat.liststrginst[b][p], \
                                                                                                                            'flux', xx=gdat.time[b][p])
                gdat.arrytser['modlnigh'+typemodl][b][p][j][:, 1] += gdat.dicterrr['amplnigh'][0, 0]
                gdat.arrytser['modlnigh'+typemodl][b][p][j][:, 1] -= gdat.arrytser['modlstel'+typemodl][b][p][j][:, 1]
                
                ### planetary modulation
                gdat.arrytser['modlpmod'+typemodl][b][p][j][:, 1] = gdat.arrytser['modlplan'+typemodl][b][p][j][:, 1] - \
                                                                                    gdat.arrytser['modlnigh'+typemodl][b][p][j][:, 1]
                    
                ### planetary residual
                gdat.arrytser['bdtrplan'+typemodl][b][p][j][:, 1] = gdat.arrytser['bdtr'][b][p][:, 1] \
                                                                                - gdat.arrytser['modlstel'+typemodl][b][p][j][:, 1] \
                                                                                - gdat.arrytser['modlelli'+typemodl][b][p][j][:, 1] \
                                                                                - gdat.arrytser['modlbeam'+typemodl][b][p][j][:, 1]
                gdat.arrytser['bdtrplan'+typemodl][b][p][j][:, 1] -= offsdays
                    
            # get allesfitter baseline model
            gdat.arrytser['modlbase'+typemodl][b][p] = np.copy(gdat.arrytser['bdtr'][b][p])
            gdat.arrytser['modlbase'+typemodl][b][p][:, 1] = gdat.objtalle[typemodl].get_posterior_median_baseline(gdat.liststrginst[b][p], 'flux', \
                                                                                                                                xx=gdat.time[b][p])
            # get allesfitter-detrended data
            gdat.arrytser['bdtr'+typemodl][b][p] = np.copy(gdat.arrytser['bdtr'][b][p])
            gdat.arrytser['bdtr'+typemodl][b][p][:, 1] = gdat.arrytser['bdtr'][b][p][:, 1] - gdat.arrytser['modlbase'+typemodl][b][p][:, 1]
            for y in gdat.indxchun[b][p]:
                # get allesfitter baseline model
                gdat.listarrytser['modlbase'+typemodl][b][p][y] = np.copy(gdat.listarrytser['bdtr'][b][p][y])
                gdat.listarrytser['modlbase'+typemodl][b][p][y][:, 1] = gdat.objtalle[typemodl].get_posterior_median_baseline(gdat.liststrginst[b][p], \
                                                                                           'flux', xx=gdat.listarrytser['modlbase'+typemodl][b][p][y][:, 0])
                # get allesfitter-detrended data
                gdat.listarrytser['bdtr'+typemodl][b][p][y] = np.copy(gdat.listarrytser['bdtr'][b][p][y])
                gdat.listarrytser['bdtr'+typemodl][b][p][y][:, 1] = gdat.listarrytser['bdtr'+typemodl][b][p][y][:, 1] - \
                                                                                gdat.listarrytser['modlbase'+typemodl][b][p][y][:, 1]
           
            print('Phase folding and binning the light curve for inference named %s...' % typemodl)
            for j in gmod.indxcomp:
                
                gdat.arrypcur['primmodltotl'+typemodl][b][p][j] = ephesus.fold_tser(gdat.arrytser['modltotl'+typemodl][b][p][j][gdat.listindxtimeclen[j][b][p], :], \
                                                                                    gdat.dicterrr['epocmtracomp'][0, j], gdat.dicterrr['pericomp'][0, j])
                
                gdat.arrypcur['primbdtr'+typemodl][b][p][j] = ephesus.fold_tser(gdat.arrytser['bdtr'+typemodl][b][p][gdat.listindxtimeclen[j][b][p], :], \
                                                                                    gdat.dicterrr['epocmtracomp'][0, j], gdat.dicterrr['pericomp'][0, j])
                
                gdat.arrypcur['primbdtr'+typemodl+'bindtotl'][b][p][j] = ephesus.rebn_tser(gdat.arrypcur['primbdtr'+typemodl][b][p][j], \
                                                                                                                    binsxdat=gdat.binsphasprimtotl)
                
                gdat.arrypcur['primbdtr'+typemodl+'bindzoom'][b][p][j] = ephesus.rebn_tser(gdat.arrypcur['primbdtr'+typemodl][b][p][j], \
                                                                                                                    binsxdat=gdat.binsphasprimzoom[j])

                for strgpcurcomp in gdat.liststrgpcurcomp + gdat.liststrgpcur:
                    
                    if strgpcurcomp in gdat.liststrgpcurcomp:
                        arrytsertemp = gdat.arrytser[strgpcurcomp+typemodl][b][p][j][gdat.listindxtimeclen[j][b][p], :]
                    else:
                        arrytsertemp = gdat.arrytser[strgpcurcomp+typemodl][b][p][gdat.listindxtimeclen[j][b][p], :]
                    
                    if strgpcurcomp == 'bdtr':
                        boolpost = True
                    else:
                        boolpost = False
                    gdat.arrypcur['quad'+strgpcurcomp+typemodl][b][p][j] = \
                                        ephesus.fold_tser(arrytsertemp, gdat.dicterrr['epocmtracomp'][0, j], gdat.dicterrr['pericomp'][0, j], phasshft=0.25) 
                
                    gdat.arrypcur['quad'+strgpcurcomp+typemodl+'bindtotl'][b][p][j] = ephesus.rebn_tser(gdat.arrypcur['quad'+strgpcurcomp+typemodl][b][p][j], \
                                                                                                                binsxdat=gdat.binsphasquadtotl)
                    
                    # write
                    path = gdat.pathdatatarg + 'arrypcurquad%sbindtotl_%s_%s.csv' % (strgpcurcomp, gdat.liststrgcomp[j], gdat.liststrginst[b][p])
                    if not os.path.exists(path):
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        np.savetxt(path, gdat.arrypcur['quad%s%sbindtotl' % (strgpcurcomp, typemodl)][b][p][j], delimiter=',', \
                                                        header='phase,%s,%s_err' % (gdat.liststrgtseralle[b], gdat.liststrgtseralle[b]))
                    
                    if gdat.boolplot:
                        plot_pser(gdat, 'quad'+strgpcurcomp+typemodl, boolpost=boolpost)
                
                
    # plots
    ## plot GP-detrended phase curves
    if gdat.boolplottser:
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                for y in gdat.indxchun[b][p]:
                    plot_tser(gdat, b, p, y, 'bdtr'+typemodl)
                    plot_pser(gdat, b, p, y, 'primbdtr'+typemodl, boolpost=True)
    if gdat.boolplotpopl:
        plot_popl(gdat, gdat.typepriocomp + typemodl)
    
    # print out transit times
    for j in gmod.indxcomp:
        print(gdat.liststrgcomp[j])
        time = np.empty(500)
        for n in range(500):
            time[n] = gdat.dicterrr['epocmtracomp'][0, j] + gdat.dicterrr['pericomp'][0, j] * n
        objttime = astropy.time.Time(time, format='jd', scale='utc')#, out_subfmt='date_hm')
        listtimelabl = objttime.iso
        for n in range(500):
            if time[n] > 2458788 and time[n] < 2458788 + 200:
                print('%f, %s' % (time[n], listtimelabl[n]))


    if typemodl == '0003' or typemodl == '0004':
            
        if typemodl == '0003':
            gdat.listlablpara = [['Nightside', 'ppm'], ['Secondary', 'ppm'], ['Planetary Modulation', 'ppm'], ['Thermal', 'ppm'], \
                                                        ['Reflected', 'ppm'], ['Phase shift', 'deg'], ['Geometric Albedo', '']]
        else:
            gdat.listlablpara = [['Nightside', 'ppm'], ['Secondary', 'ppm'], ['Thermal', 'ppm'], \
                                  ['Reflected', 'ppm'], ['Thermal Phase shift', 'deg'], ['Reflected Phase shift', 'deg'], ['Geometric Albedo', '']]
        numbpara = len(gdat.listlablpara)
        indxpara = np.arange(numbpara)
        listpost = np.empty((gdat.numbsamp, numbpara))
        
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                for j in gmod.indxcomp:
                    listpost[:, 0] = gdat.dictlist['amplnigh'][:, j] * 1e6 # [ppm]
                    listpost[:, 1] = gdat.dictlist['amplseco'][:, j] * 1e6 # [ppm]
                    if typemodl == '0003':
                        listpost[:, 2] = gdat.dictlist['amplplan'][:, j] * 1e6 # [ppm]
                        listpost[:, 3] = gdat.dictlist['amplplanther'][:, j] * 1e6 # [ppm]
                        listpost[:, 4] = gdat.dictlist['amplplanrefl'][:, j] * 1e6 # [ppm]
                        listpost[:, 5] = gdat.dictlist['phasshftplan'][:, j]
                        listpost[:, 6] = gdat.dictlist['albg'][:, j]
                    else:
                        listpost[:, 2] = gdat.dictlist['amplplanther'][:, j] * 1e6 # [ppm]
                        listpost[:, 3] = gdat.dictlist['amplplanrefl'][:, j] * 1e6 # [ppm]
                        listpost[:, 4] = gdat.dictlist['phasshftplanther'][:, j]
                        listpost[:, 5] = gdat.dictlist['phasshftplanrefl'][:, j]
                        listpost[:, 6] = gdat.dictlist['albg'][:, j]
                    tdpy.plot_grid(gdat.pathalle[typemodl], 'pcur_%s' % typemodl, listpost, gdat.listlablpara, plotsize=2.5)

        # plot phase curve
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                
                ## determine data gaps for overplotting model without the data gaps
                gdat.indxtimegapp = np.argmax(gdat.time[b][p][1:] - gdat.time[b][p][:-1]) + 1
                
                for j in gmod.indxcomp:
                    path = gdat.pathalle[typemodl] + 'pcur_grid_%s_%s_%s.%s' % (typemodl, gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+2].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                    if not os.path.exists(path):
                        figr = plt.figure(figsize=(10, 12))
                        axis = [[] for k in range(3)]
                        axis[0] = figr.add_subplot(3, 1, 1)
                        axis[1] = figr.add_subplot(3, 1, 2)
                        axis[2] = figr.add_subplot(3, 1, 3, sharex=axis[1])
                        
                        for k in range(len(axis)):
                            
                            ## unbinned data
                            if k < 2:
                                if k == 0:
                                    xdat = gdat.time[b][p] - gdat.timeoffs
                                    ydat = gdat.arrytser['bdtr'+typemodl][b][p][:, 1] + gdat.dicterrr['amplnigh'][0, 0]
                                if k == 1:
                                    xdat = gdat.arrypcur['quadbdtr'+typemodl][b][p][j][:, 0]
                                    ydat = gdat.arrypcur['quadbdtr'+typemodl][b][p][j][:, 1] + gdat.dicterrr['amplnigh'][0, 0]
                                axis[k].plot(xdat, ydat, '.', color='grey', alpha=0.3, label='Raw data')
                            
                            ## binned data
                            if k > 0:
                                xdat = gdat.arrypcur['quadbdtr'+typemodl+'bindtotl'][b][p][j][:, 0]
                                ydat = gdat.arrypcur['quadbdtr'+typemodl+'bindtotl'][b][p][j][:, 1] + gdat.dicterrr['amplnigh'][0, 0]
                                yerr = np.copy(gdat.arrypcur['quadbdtr'+typemodl+'bindtotl'][b][p][j][:, 2])
                            else:
                                xdat = None
                                ydat = None
                                yerr = None
                            if k == 2:
                                ydat = (ydat - 1) * 1e6
                                yerr *= 1e6
                            # temp - add offset to bring the base of secondary to 0 
                            axis[k].errorbar(xdat, ydat, marker='o', yerr=yerr, capsize=0, ls='', color='k', label='Binned data')
                            
                            ## model
                            if k > 0:
                                xdat = gdat.arrypcur['quadmodl'+typemodl][b][p][j][:, 0]
                                ydat = gdat.arrypcur['quadmodl'+typemodl][b][p][j][:, 1] + gdat.dicterrr['amplnigh'][0, 0]
                            else:
                                xdat = gdat.arrytser['modltotl'+typemodl][b][p][j][:, 0] - gdat.timeoffs
                                ydat = gdat.arrytser['modltotl'+typemodl][b][p][j][:, 1] + gdat.dicterrr['amplnigh'][0, 0]
                            if k == 2:
                                ydat = (ydat - 1) * 1e6
                            if k == 0:
                                axis[k].plot(xdat[:gdat.indxtimegapp], ydat[:gdat.indxtimegapp], color='b', lw=2, label='Total Model', zorder=10)
                                axis[k].plot(xdat[gdat.indxtimegapp:], ydat[gdat.indxtimegapp:], color='b', lw=2, zorder=10)
                            else:
                                axis[k].plot(xdat, ydat, color='b', lw=2, label='Model', zorder=10)
                            
                            # add Vivien's result
                            if k == 2 and gdat.labltarg == 'WASP-121':
                                axis[k].plot(gdat.phasvivi, gdat.deptvivi*1e3, color='orange', lw=2, label='GCM (Parmentier+2018)')
                                axis[k].axhline(0., ls='-.', alpha=0.3, color='grey')

                            if k == 0:
                                axis[k].set(xlabel='Time [BJD - %d]' % gdat.timeoffs)
                            if k > 0:
                                axis[k].set(xlabel='Phase')
                        axis[0].set(ylabel=gdat.labltserphot)
                        axis[1].set(ylabel=gdat.labltserphot)
                        axis[2].set(ylabel='Relative flux - 1 [ppm]')
                        
                        if gdat.labltarg == 'WASP-121':
                            ylimpcur = [-400, 1000]
                        else:
                            ylimpcur = [-100, 300]
                        axis[2].set_ylim(ylimpcur)
                        
                        xdat = gdat.arrypcur['quadmodlstel'+typemodl][b][p][j][:, 0]
                        ydat = (gdat.arrypcur['quadmodlstel'+typemodl][b][p][j][:, 1] - 1.) * 1e6
                        axis[2].plot(xdat, ydat, lw=2, color='orange', label='Stellar baseline', ls='--', zorder=11)
                        
                        xdat = gdat.arrypcur['quadmodlelli'+typemodl][b][p][j][:, 0]
                        ydat = (gdat.arrypcur['quadmodlelli'+typemodl][b][p][j][:, 1] - 1.) * 1e6
                        axis[2].plot(xdat, ydat, lw=2, color='r', ls='--', label='Ellipsoidal variation')
                        
                        xdat = gdat.arrypcur['quadmodlelli'+typemodl][b][p][j][:, 0]
                        ydat = (gdat.arrypcur['quadmodlelli'+typemodl][b][p][j][:, 1] - 1.) * 1e6
                        axis[2].plot(xdat, ydat, lw=2, color='r', ls='--', label='Ellipsoidal variation')
                        
                        xdat = gdat.arrypcur['quadmodlplan'+typemodl][b][p][j][:, 0]
                        ydat = (gdat.arrypcur['quadmodlplan'+typemodl][b][p][j][:, 1] - 1.) * 1e6
                        axis[2].plot(xdat, ydat, lw=2, color='g', label='Planetary', ls='--')
    
                        xdat = gdat.arrypcur['quadmodlnigh'+typemodl][b][p][j][:, 0]
                        ydat = (gdat.arrypcur['quadmodlnigh'+typemodl][b][p][j][:, 1] - 1.) * 1e6
                        axis[2].plot(xdat, ydat, lw=2, color='olive', label='Planetary baseline', ls='--', zorder=11)
    
                        xdat = gdat.arrypcur['quadmodlpmod'+typemodl][b][p][j][:, 0]
                        ydat = (gdat.arrypcur['quadmodlpmod'+typemodl][b][p][j][:, 1] - 1.) * 1e6
                        axis[2].plot(xdat, ydat, lw=2, color='m', label='Planetary modulation', ls='--', zorder=11)
                         
                        ## legend
                        axis[2].legend(ncol=3)
                        
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        plt.savefig(path)
                        plt.close()
                   

        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                for j in gmod.indxcomp:
        
                    path = gdat.pathalle[typemodl] + 'pcur_samp_%s_%s_%s.%s' % (typemodl, gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    if not os.path.exists(path):
                        # replot phase curve
                        ### sample model phas
                        #numbphasfine = 1000
                        #gdat.meanphasfine = np.linspace(np.amin(gdat.arrypcur['quadbdtr'][0][gdat.indxphasotpr, 0]), \
                        #                                np.amax(gdat.arrypcur['quadbdtr'][0][gdat.indxphasotpr, 0]), numbphasfine)
                        #indxphasfineinse = np.where(abs(gdat.meanphasfine - 0.5) < phasseco)[0]
                        #indxphasfineotprleft = np.where(-gdat.meanphasfine > phasmask)[0]
                        #indxphasfineotprrght = np.where(gdat.meanphasfine > phasmask)[0]
       
                        indxphasmodlouttprim = [[] for a in range(2)]
                        indxphasdatabindouttprim = [[] for a in range(2)]
                        indxphasmodlouttprim[0] = np.where(gdat.arrypcur['quadmodl'+typemodl][b][p][j][:, 0] < -0.05)[0]
                        indxphasdatabindouttprim[0] = np.where(gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 0] < -0.05)[0]
                        indxphasmodlouttprim[1] = np.where(gdat.arrypcur['quadmodl'+typemodl][b][p][j][:, 0] > 0.05)[0]
                        indxphasdatabindouttprim[1] = np.where(gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 0] > 0.05)[0]

                    path = gdat.pathalle[typemodl] + 'pcur_comp_%s_%s_%s.%s' % (typemodl, gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+2].append({'path': path, 'limt':[0., 0.05, 0.5, 0.1]})
                    if not os.path.exists(path):
                        # plot the phase curve with components
                        figr, axis = plt.subplots(figsize=gdat.figrsizeydob)
                        ## data
                        axis.errorbar(gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 0], \
                                       (gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 1] + gdat.dicterrr['amplnigh'][0, 0] - 1) * 1e6, \
                                       yerr=1e6*gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 2], color='k', marker='o', ls='', markersize=2, lw=1, label='Data')
                        ## total model
                        axis.plot(gdat.arrypcur['quadmodl'+typemodl][b][p][j][:, 0], \
                                                        1e6*(gdat.arrypcur['quadmodl'+typemodl][b][p][j][:, 1]+gdat.dicterrr['amplnigh'][0, 0]-1), \
                                                                                                                        color='b', lw=3, label='Model')
                        
                        axis.plot(gdat.arrypcur['quadmodlplan'+typemodl][b][p][j][:, 0], 1e6*(gdat.arrypcur['quadmodlplan'+typemodl][b][p][j][:, 1]), \
                                                                                                                      color='g', label='Planetary', lw=1, ls='--')
                        
                        axis.plot(gdat.arrypcur['quadmodlbeam'+typemodl][b][p][j][:, 0], 1e6*(gdat.arrypcur['quadmodlbeam'+typemodl][b][p][j][:, 1]), \
                                                                                                              color='m', label='Beaming', lw=2, ls='--')
                        
                        axis.plot(gdat.arrypcur['quadmodlelli'+typemodl][b][p][j][:, 0], 1e6*(gdat.arrypcur['quadmodlelli'+typemodl][b][p][j][:, 1]), \
                                                                                                              color='r', label='Ellipsoidal variation', lw=2, ls='--')
                        
                        axis.plot(gdat.arrypcur['quadmodlstel'+typemodl][b][p][j][:, 0], 1e6*(gdat.arrypcur['quadmodlstel'+typemodl][b][p][j][:, 1]-1.), \
                                                                                                              color='orange', label='Stellar baseline', lw=2, ls='--')
                        
                        axis.set_ylim(ylimpcur)
                        axis.set_ylabel('Relative flux [ppm]')
                        axis.set_xlabel('Phase')
                        axis.legend(ncol=3)
                        plt.tight_layout()
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        plt.savefig(path)
                        plt.close()

                    path = gdat.pathalle[typemodl] + 'pcur_samp_%s_%s_%s.%s' % (typemodl, gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+2].append({'path': path, 'limt':[0., 0.05, 0.5, 0.1]})
                    if not os.path.exists(path):
                        # plot the phase curve with samples
                        figr, axis = plt.subplots(figsize=gdat.figrsizeydob)
                        axis.errorbar(gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 0], \
                                    (gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 1] + gdat.dicterrr['amplnigh'][0, 0] - 1) * 1e6, \
                                                     yerr=1e6*gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 2], color='k', marker='o', ls='', markersize=2, lw=1)
                        for ii, i in enumerate(gdat.indxsampplot):
                            axis.plot(gdat.arrypcur['quadmodl'+typemodl][b][p][j][:, 0], \
                                                        1e6 * (gdat.listarrypcur['quadmodl'+typemodl][b][p][j][ii, :] + gdat.dicterrr['amplnigh'][0, 0] - 1.), \
                                                                                                                                          alpha=0.1, color='b')
                        axis.set_ylabel('Relative flux [ppm]')
                        axis.set_xlabel('Phase')
                        axis.set_ylim(ylimpcur)
                        plt.tight_layout()
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        plt.savefig(path)
                        plt.close()

                    # plot all along with residuals
                    #path = gdat.pathalle[typemodl] + 'pcur_resi_%s_%s_%s.%s' % (typemodl, gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                    #if not os.path.exists(path):
                    #   figr, axis = plt.subplots(3, 1, figsize=gdat.figrsizeydob)
                    #   axis.errorbar(gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 0], (gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 1]) * 1e6, \
                    #                          yerr=1e6*gdat.arrypcur['quadbdtrbindtotl'][b][p][j][:, 2], color='k', marker='o', ls='', markersize=2, lw=1)
                    #   for kk, k in enumerate(gdat.indxsampplot):
                    #       axis.plot(gdat.meanphasfine[indxphasfineotprleft], (listmodltotl[k, indxphasfineotprleft] - listoffs[k]) * 1e6, \
                    #                                                                                                               alpha=0.1, color='b')
                    #       axis.plot(gdat.meanphasfine[indxphasfineotprrght], (listmodltotl[k, indxphasfineotprrght] - listoffs[k]) * 1e6, \
                    #                                                                                                               alpha=0.1, color='b')
                    #   axis.set_ylabel('Relative flux - 1 [ppm]')
                    #   axis.set_xlabel('Phase')
                    #   plt.tight_layout()
                    #   print('Writing to %s...' % path)
                    #   plt.savefig(path)
                    #   plt.close()

                    # write to text file
                    path = gdat.pathalle[typemodl] + 'post_pcur_%s_tabl.csv' % (typemodl)
                    if not os.path.exists(path):
                        fileoutp = open(gdat.pathalle[typemodl] + 'post_pcur_%s_tabl.csv' % (typemodl), 'w')
                        for strgfeat in gdat.dictlist:
                            if gdat.dictlist[strgfeat].ndim == 2:
                                for j in gmod.indxcomp:
                                    fileoutp.write('%s,%s,%g,%g,%g,%g,%g\\\\\n' % (strgfeat, gdat.liststrgcomp[j], gdat.dictlist[strgfeat][0, j], gdat.dictlist[strgfeat][1, j], \
                                                                                gdat.dictlist[strgfeat][2, j], gdat.dicterrr[strgfeat][1, j], gdat.dicterrr[strgfeat][2, j]))
                            else:
                                fileoutp.write('%s,,%g,%g,%g,%g,%g\\\\\n' % (strgfeat, gdat.dictlist[strgfeat][0], gdat.dictlist[strgfeat][1], \
                                                                                gdat.dictlist[strgfeat][2], gdat.dicterrr[strgfeat][1], gdat.dicterrr[strgfeat][2]))
                            #fileoutp.write('\\\\\n')
                        fileoutp.close()
                    
                    path = gdat.pathalle[typemodl] + 'post_pcur_%s_cmnd.csv' % (typemodl)
                    if not os.path.exists(path):
                        fileoutp = open(gdat.pathalle[typemodl] + 'post_pcur_%s_cmnd.csv' % (typemodl), 'w')
                        for strgfeat in gdat.dictlist:
                            if gdat.dictlist[strgfeat].ndim == 2:
                                for j in gmod.indxcomp:
                                    fileoutp.write('%s,%s,$%.3g \substack{+%.3g \\\\ -%.3g}$\\\\\n' % (strgfeat, gdat.liststrgcomp[j], gdat.dicterrr[strgfeat][0, j], \
                                                                                                gdat.dicterrr[strgfeat][1, j], gdat.dicterrr[strgfeat][2, j]))
                            else:
                                fileoutp.write('%s,,$%.3g \substack{+%.3g \\\\ -%.3g}$\\\\\n' % (strgfeat, gdat.dicterrr[strgfeat][0], \
                                                                                                            gdat.dicterrr[strgfeat][1], gdat.dicterrr[strgfeat][2]))
                            #fileoutp.write('\\\\\n')
                        fileoutp.close()

                if typemodl == '0003':
                    
                    # wavelength axis
                    gdat.conswlentmpt = 0.0143877735e6 # [um K]

                    minmalbg = min(np.amin(gdat.dictlist['albginfo']), np.amin(gdat.dictlist['albg']))
                    maxmalbg = max(np.amax(gdat.dictlist['albginfo']), np.amax(gdat.dictlist['albg']))
                    binsalbg = np.linspace(minmalbg, maxmalbg, 100)
                    meanalbg = (binsalbg[1:] + binsalbg[:-1]) / 2.
                    pdfnalbg = tdpy.retr_kdegpdfn(gdat.dictlist['albg'][:, 0], binsalbg, 0.02)
                    pdfnalbginfo = tdpy.retr_kdegpdfn(gdat.dictlist['albginfo'][:, 0], binsalbg, 0.02)
                    
                    path = gdat.pathalle[typemodl] + 'pdfn_albg_%s_%s.%s' % (gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                    if not os.path.exists(path):
                        figr, axis = plt.subplots(figsize=gdat.figrsizeydob)
                        axis.plot(meanalbg, pdfnalbg, label='TESS only', lw=2)
                        axis.plot(meanalbg, pdfnalbginfo, label='TESS + ATMO', lw=2)
                        axis.set_xlabel('$A_g$')
                        axis.set_ylabel('$P(A_g)$')
                        axis.legend()
                        axis.set_xlim([0, None])
                        plt.subplots_adjust()
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        plt.savefig(path)
                        plt.close()
                
                    path = gdat.pathalle[typemodl] + 'hist_albg_%s_%s.%s' % (gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                    if not os.path.exists(path):
                        figr, axis = plt.subplots(figsize=gdat.figrsizeydob)
                        axis.hist(gdat.dictlist['albg'][:, 0], label='TESS only', bins=binsalbg)
                        axis.hist(gdat.dictlist['albginfo'][:, 0], label='TESS + ATMO', bins=binsalbg)
                        axis.set_xlabel('$A_g$')
                        axis.set_ylabel('$N(A_g)$')
                        axis.legend()
                        plt.subplots_adjust()
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        plt.savefig(path)
                        plt.close()
                
                    #liststrgfile = ['ContribFuncArr.txt', \
                    #                'EmissionDataArray.txt', \
                    #                #'RetrievalParamSamples.txt', \
                    #                'ContribFuncWav.txt', \
                    #                'EmissionModelArray.txt', \
                    #                'RetrievalPTSamples.txt', \
                    #                'pdependent_abundances/', \
                    #                ]
                    
                    # get the ATMO posterior
                    path = gdat.pathdatatarg + 'ascii_output/RetrievalParamSamples.txt'
                    listsampatmo = np.loadtxt(path)
                    
                    # plot ATMO posterior
                    gdat.listlablpara = [['$\kappa_{IR}$', ''], ['$\gamma$', ''], ['$\psi$', ''], ['[M/H]', ''], \
                                                                                                    ['[C/H]', ''], ['[O/H]', '']]
                    tdpy.plot_grid(gdat.pathalle[typemodl], 'post_atmo', listsampatmo, gdat.listlablpara, plotsize=2.5)
   
                    # get the ATMO posterior on irradiation efficiency, psi
                    indxsampatmo = np.random.choice(np.arange(listsampatmo.shape[0]), size=gdat.numbsamp, replace=False)
                    gdat.listpsii = listsampatmo[indxsampatmo, 2]
                    
                    gdat.gmeatmptequi = np.percentile(gdat.dictlist['tmptequi'][:, 0], 50.)
                    gdat.gstdtmptequi = (np.percentile(gdat.dictlist['tmptequi'][:, 0], 84.) - np.percentile(gdat.dictlist['tmptequi'][:, 0], 16.)) / 2.
                    gdat.gmeatmptdayy = np.percentile(gdat.dictlist['tmptdayy'][:, 0], 50.)
                    gdat.gstdtmptdayy = (np.percentile(gdat.dictlist['tmptdayy'][:, 0], 84.) - np.percentile(gdat.dictlist['tmptdayy'][:, 0], 16.)) / 2.
                    gdat.gmeatmptnigh = np.percentile(gdat.dictlist['tmptnigh'][:, 0], 50.)
                    gdat.gstdtmptnigh = (np.percentile(gdat.dictlist['tmptnigh'][:, 0], 84.) - np.percentile(gdat.dictlist['tmptnigh'][:, 0], 16.)) / 2.
                    gdat.gmeapsii = np.percentile(gdat.listpsii, 50.)
                    gdat.gstdpsii = (np.percentile(gdat.listpsii, 84.) - np.percentile(gdat.listpsii, 16.)) / 2.
                
                    histpsii, gdat.binspsii = np.histogram(gdat.listpsii, 1001)
                    gdat.meanpsii = (gdat.binspsii[1:] + gdat.binspsii[:-1]) / 2.
                    
                    gdat.kdegstdvpsii = 0.01
                    path = gdat.pathalle[typemodl] + 'kdeg_psii_%s_%s.%s' % (gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                    if not os.path.exists(path):
                        figr, axis = plt.subplots(figsize=gdat.figrsizeydob)
                        gdat.kdegpsii = tdpy.retr_kdeg(gdat.listpsii, gdat.meanpsii, gdat.kdegstdvpsii)
                        axis.plot(gdat.meanpsii, gdat.kdegpsii)
                        axis.set_xlabel('$\psi$')
                        axis.set_ylabel('$K_\psi$')
                        plt.subplots_adjust()
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        plt.savefig(path)
                        plt.close()
                
                    # use psi posterior to infer Bond albedo and heat circulation efficiency
                    numbsampwalk = 10000
                    numbsampburnwalk = 1000
                    gdat.listlablpara = [['$A_b$', ''], ['$E$', ''], [r'$\varepsilon$', '']]
                    listscalpara = ['self', 'self', 'self']
                    gdat.listminmpara = np.array([0., 0., 0.])
                    gdat.listmaxmpara = np.array([1., 1., 1.])
                    strgextn = 'albbepsi'
                    listpostheat = tdpy.samp(gdat, numbsampwalk, retr_llik_albbepsi, \
                                                  gdat.listlablpara, listscalpara, gdat.listminmpara, gdat.listmaxmpara, boolplot=gdat.boolplot, \
                                                  pathbase=gdat.pathtargruns, \
                                                  typeverb=gdat.typeverb, \
                                                  numbsampburnwalk=numbsampburnwalk, strgextn=strgextn)

                    # plot emission spectra, secondary eclipse depth, and brightness temperature
                    #listcolr = ['k', 'm', 'purple', 'olive', 'olive', 'r', 'g']
                    listcolr = ['k', 'm', 'purple', 'olive', 'olive', 'r', 'g']
                    for i in range(15):
                        listcolr.append('r')
                    for i in range(28):
                        listcolr.append('g')
                    figr, axis = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
                    ## stellar emission spectrum and TESS throughput
                    axis[0].plot(arrymodl[:, 0], 1e-9 * arrymodl[:, 9], label='Host star', color='grey')
                    axis[0].plot(0., 0., ls='--', label='TESS Throughput', color='grey')
                    axis[0].set_ylabel(r'$\nu F_{\nu}$ [10$^9$ erg/s/cm$^2$]')
                    axis[0].legend(fancybox=True, bbox_to_anchor=[0.7, 0.22, 0.2, 0.2])
                    axistwin = axis[0].twinx()
                    axistwin.plot(gdat.meanwlenband, gdat.thptband, color='grey', ls='--', label='TESS')
                    axistwin.set_ylabel(r'Throughput')
                    
                    ## secondary eclipse depths
                    ### model
                    objtplotmodllavgd, = axis[1].plot(arrydata[0, 0], 1e6*gdat.amplplantheratmo, color='b', marker='D')
                    axis[1].plot(arrymodl[:, 0], arrymodl[:, 1], label='1D Retrieval (This work)', color='b')
                    axis[1].plot(arrymodl[:, 0], arrymodl[:, 2], label='Blackbody (This work)', alpha=0.3, color='deepskyblue')
                    axis[1].fill_between(arrymodl[:, 0], arrymodl[:, 3], arrymodl[:, 4], alpha=0.3, color='deepskyblue')
                    objtplotvivi, = axis[1].plot(gdat.wlenvivi, gdat.specvivi * 1e6, color='orange', alpha=0.6, lw=2)
                    ### data
                    for k in range(5):
                        axis[1].errorbar(arrydata[k, 0], arrydata[k, 2], xerr=arrydata[k, 1], yerr=arrydata[k, 3], ls='', marker='o', color=listcolr[k])
                    axis[1].errorbar(arrydata[5:22, 0], arrydata[5:22, 2], xerr=arrydata[5:22, 1], yerr=arrydata[5:22, 3], ls='', marker='o', color='r')
                    axis[1].errorbar(arrydata[22:-1, 0], arrydata[22:-1, 2], xerr=arrydata[22:-1, 1], yerr=arrydata[22:-1, 3], ls='', marker='o', color='g')
                    axis[1].set_ylabel(r'Depth [ppm]')
                    axis[1].set_xticklabels([])
                    
                    ## planetary emission spectra
                    ### model
                    objtplotretr, = axis[2].plot(arrymodl[:, 0], 1e-9 * arrymodl[:, 5], label='1D Retrieval (This work)', color='b')
                    objtplotmblc, = axis[2].plot(arrymodl[:, 0], 1e-9 * arrymodl[:, 6], label='Blackbody (This work)', color='deepskyblue', alpha=0.3)
                    objtploteblc = axis[2].fill_between(arrymodl[:, 0], 1e-9 * arrymodl[:, 7], 1e-9 * arrymodl[:, 8], color='deepskyblue', alpha=0.3)
                    axis[2].legend([objtplotretr, objtplotmodllavgd, (objtplotmblc, objtploteblc), objtplotvivi], \
                                               ['1D Retrieval (This work)', '1D Retrieval (This work), Avg', 'Blackbody (This work)', 'GCM (Parmentier+2018)'], \
                                                                                            bbox_to_anchor=[0.8, 1.4, 0.2, 0.2])
                    ### data
                    for k in range(5):
                        axis[2].errorbar(arrydata[k, 0],  1e-9 * arrydata[k, 6], xerr=arrydata[k, 1], yerr=1e-9*arrydata[k, 7], ls='', marker='o', color=listcolr[k])
                    axis[2].errorbar(arrydata[5:22, 0], 1e-9 * arrydata[5:22, 6], xerr=arrydata[5:22, 1], yerr=1e-9*arrydata[5:22, 7], ls='', marker='o', color='r')
                    axis[2].errorbar(arrydata[22:-1, 0], 1e-9 * arrydata[22:-1, 6], xerr=arrydata[22:-1, 1], \
                                                                    yerr=1e-9*arrydata[22:-1, 7], ls='', marker='o', color='g')
                    
                    axis[2].set_ylabel(r'$\nu F_{\nu}$ [10$^9$ erg/s/cm$^2$]')
                    axis[2].set_xticklabels([])
                    
                    ## brightness temperature
                    ### data
                    for k in range(5):
                        if k == 0:
                            labl = 'TESS (This work)'
                        if k == 1:
                            labl = 'Z$^\prime$ (Delrez+2016)'
                        if k == 2:
                            labl = '$K_s$ (Kovacs\&Kovacs2019)'
                        if k == 3:
                            labl = 'IRAC $\mu$m (Garhart+2019)'
                        #if k == 4:
                        #    labl = 'IRAC 4.5 $\mu$m (Garhart+2019)'
                        axis[3].errorbar(arrydata[k, 0], arrydata[k, 4], xerr=arrydata[k, 1], yerr=arrydata[k, 5], label=labl, ls='', marker='o', color=listcolr[k])
                    axis[3].errorbar(arrydata[5:22, 0], arrydata[5:22, 4], xerr=arrydata[5:22, 1], \
                                                         yerr=arrydata[5:22, 5], label='HST G102 (Evans+2019)', ls='', marker='o', color='r')
                    axis[3].errorbar(arrydata[22:-1, 0], arrydata[22:-1, 4], xerr=arrydata[22:-1, 1], \
                                                        yerr=arrydata[22:-1, 5], label='HST G141 (Evans+2017)', ls='', marker='o', color='g')
                    #axis[3].errorbar(arrydata[:, 0], np.median(tmpt, 0), xerr=arrydata[:, 1], yerr=np.std(tmpt, 0), label='My calc', ls='', marker='o', color='c')
                    axis[3].set_ylabel(r'$T_B$ [K]')
                    axis[3].set_xlabel(r'$\lambda$ [$\mu$m]')
                    axis[3].legend(fancybox=True, bbox_to_anchor=[0.8, 3.8, 0.2, 0.2], ncol=2)
                    
                    axis[1].set_ylim([20, None])
                    axis[1].set_yscale('log')
                    for i in range(4):
                        axis[i].set_xscale('log')
                    axis[3].set_xlim([0.5, 5])
                    axis[3].xaxis.set_minor_formatter(mpl.ticker.ScalarFormatter())
                    axis[3].xaxis.set_major_formatter(mpl.ticker.ScalarFormatter())
                    plt.subplots_adjust(hspace=0., wspace=0.)
                    path = gdat.pathalle[typemodl] + 'spec_%s_%s.%s' % (gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                    if gdat.typeverb > 0:
                        print('Writing to %s...' % path)
                    plt.savefig(path)
                    plt.close()
                    
                    # get contribution function
                    path = gdat.pathdatatarg + 'ascii_output/ContribFuncArr.txt'
                    if gdat.typeverb > 0:
                        print('Reading from %s...' % path)
                    ctrb = np.loadtxt(path)
                    presctrb = ctrb[0, :]
                    # interpolate the throughput
                    gdat.thptbandctrb = scipy.interpolate.interp1d(gdat.meanwlenband, gdat.thptband, fill_value=0, bounds_error=False)(wlenctrb)
                    numbwlenctrb = wlenctrb.size
                    indxwlenctrb = np.arange(numbwlenctrb)
                    numbpresctrb = presctrb.size
                    indxpresctrb = np.arange(numbpresctrb)

                    # plot pressure-temperature, contribution function, abundances
                    ## get ATMO posterior
                    path = gdat.pathdatatarg + 'ascii_output/RetrievalPTSamples.txt'
                    dataptem = np.loadtxt(path)
                    liststrgcomp = ['CH4.txt', 'CO.txt', 'FeH.txt', 'H+.txt', 'H.txt', 'H2.txt', 'H2O.txt', 'H_.txt', 'He.txt', 'K+.txt', \
                                                                        'K.txt', 'NH3.txt', 'Na+.txt', 'Na.txt', 'TiO.txt', 'VO.txt', 'e_.txt']
                    listlablcomp = ['CH$_4$', 'CO', 'FeH', 'H$^+$', 'H', 'H$_2$', 'H$_2$O', 'H$^-$', 'He', 'K$^+$', \
                                                                        'K', 'NH$_3$', 'Na$^+$', 'Na', 'TiO', 'VO', 'e$^-$']
                    listdatacomp = []
                    for strg in liststrgcomp:
                        path = gdat.pathdatatarg + 'ascii_output/pdependent_abundances/' + strg
                        listdatacomp.append(np.loadtxt(path))
                    ## plot
                    figr, axis = plt.subplots(nrows=1, ncols=2, sharey=True, gridspec_kw={'width_ratios': [1, 2]}, figsize=gdat.figrsizeydob)
                    ### pressure temperature
                    numbsamp = dataptem.shape[0] - 1
                    indxsamp = np.arange(numbsamp)
                    for i in indxsamp[::100]:
                        axis[0].plot(dataptem[i, :], dataptem[0, :], color='b', alpha=0.1)
                    axis[0].plot(np.percentile(dataptem, 10, axis=0), dataptem[0, :], color='g')
                    axis[0].plot(np.percentile(dataptem, 50, axis=0), dataptem[0, :], color='r')
                    axis[0].plot(np.percentile(dataptem, 90, axis=0), dataptem[0, :], color='g')
                    axis[0].set_xlim([1500, 3700])
                    axis[0].set_xlabel('$T$ [K]')
                    axis[0].set_yscale('log')
                    axis[0].set_ylabel('$P$ [bar]')
                    axis[0].invert_yaxis()
                    axis[0].set_ylim([10., 1e-5])
                    ### contribution function
                    axistwin = axis[0].twiny()
                    ctrbtess = np.empty(numbpresctrb)
                    for k in indxpresctrb:
                        ctrbtess[k] = np.sum(ctrb[1:, k] * gdat.thptbandctrb)
                    ctrbtess *= 1e-12 / np.amax(ctrbtess)
                    axistwin.fill(ctrbtess, presctrb, alpha=0.5, color='grey')
                    axistwin.set_xticklabels([])
                    ## abundances
                    numbcomp = len(listdatacomp)
                    indxcomp = np.arange(numbcomp)
                    listobjtcolr = sns.color_palette('hls', numbcomp)
                    axis[1].set_prop_cycle('color', listobjtcolr)
                    listcolr = []
                    for k in indxcomp:
                        objt, = axis[1].plot(listdatacomp[k][:, 1], listdatacomp[k][:, 0])
                        listcolr.append(objt.get_color())

                    axis[1].xaxis.tick_top()
                    
                    arry = np.logspace(-16., 0., 21) # x 0.8
                    for k in range(21):
                        axis[1].axvline(arry[k], ls='--', alpha=0.1, color='k')
                    arry = np.logspace(-5., 1., 11) # y 0.6
                    for k in range(11):
                        axis[1].axhline(arry[k], ls='--', alpha=0.1, color='k')
                    listobjtcolr = sns.color_palette('hls', numbcomp)
                    axis[1].set_prop_cycle('color', listobjtcolr)
                    for k in indxcomp:
                        if k == 0: # CH4
                            xpos, ypos = 10**-12.8, 10**-2.3
                        elif k == 1: # CO
                            xpos, ypos = 10**-2.8, 10**-3.5
                        elif k == 2: # FeH
                            xpos, ypos = 10**-10.8, 10**-3.5
                        elif k == 3: # H+
                            xpos, ypos = 10**-12.8, 10**-4.1
                        elif k == 4: # H
                            xpos, ypos = 10**-1.6, 10**-2
                        elif k == 5: # H2
                            xpos, ypos = 10**-1.6, 10**-2.6
                        elif k == 6: # H20
                            xpos, ypos = 10**-8.8, 10**-4.1
                        elif k == 7: # H_
                            xpos, ypos = 10**-10., 10**0.4
                        elif k == 8: # He
                            xpos, ypos = 10**-1.6, 10**-4.1
                        elif k == 9: # K+
                            xpos, ypos = 10**-4.4, 10**-4.8
                        elif k == 10: # K
                            xpos, ypos = 10**-8.4, 10**-4.8
                        elif k == 11: # Nh3
                            xpos, ypos = 10**-13.6, 10**-4.1
                        elif k == 12: # Na+
                            xpos, ypos = 10**-4.4, 10**-3.8
                        elif k == 13: # Na
                            xpos, ypos = 10**-6, 10**-3.8
                        elif k == 14: # TiO
                            xpos, ypos = 10**-7.6, 10**-2
                        elif k == 15: # VO
                            xpos, ypos = 10**-6, 10**-2
                        elif k == 16: # e-
                            xpos, ypos = 10**-5.6, 10**-0.8
                        else:
                            xpos = 10**(np.random.rand() * 16. - 16.)
                            ypos = 10**(np.random.rand() * 6. - 5.)
                        axis[1].text(xpos, ypos, '%s' % listlablcomp[k], color=listcolr[k], size=10, va='center', ha='center')
                    axis[1].set_xscale('log')
                    axis[1].set_xlabel('Volume Mixing Ratio')
                    axis[1].set_yscale('log')
                    axis[1].set_xlim([1e-16, 1])
                    plt.subplots_adjust(hspace=0., wspace=0., bottom=0.15)
                    path = gdat.pathalle[typemodl] + 'ptem_%s_%s.%s' % (gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
                    gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                    if gdat.typeverb > 0:
                        print('Writing to %s...' % path)
                    plt.savefig(path)
                    plt.close()
  

def plot_popl(gdat, strgpdfn):
    
    print('Plotting target features along with population features for strgpdfn: %s' % strgpdfn)
        
    pathimagfeatplan = getattr(gdat, 'pathimagfeatplan' + strgpdfn)
    pathimagdataplan = getattr(gdat, 'pathimagdataplan' + strgpdfn)
    pathimagfeatsyst = getattr(gdat, 'pathimagfeatsyst' + strgpdfn)
    
    ## occurence rate as a function of planet radius with highlighted radii of the system's planets
    ### get the CKS occurence rate as a function of planet radius
    path = gdat.pathbasemile + 'data/Fulton+2017/Means.csv'
    data = np.loadtxt(path, delimiter=',')
    timeoccu = data[:, 0]
    occumean = data[:, 1]
    path = gdat.pathbasemile + 'data/Fulton+2017/Lower.csv'
    occulowr = np.loadtxt(path, delimiter=',')
    occulowr = occulowr[:, 1]
    path = gdat.pathbasemile + 'data/Fulton+2017/Upper.csv'
    occuuppr = np.loadtxt(path, delimiter=',')
    occuuppr = occuuppr[:, 1]
    occuyerr = np.empty((2, occumean.size))
    occuyerr[0, :] = occuuppr - occumean
    occuyerr[1, :] = occumean - occulowr
    
    figr, axis = plt.subplots(figsize=gdat.figrsize)
    
    # this system
    for jj, j in enumerate(gmod.indxcomp):
        if strgpdfn == 'post':
            xposlowr = gdat.dictpost['radicomp'][0, j]
            xposmedi = gdat.dictpost['radicomp'][1, j]
            xposuppr = gdat.dictpost['radicomp'][2, j]
        else:
            xposmedi = gdat.rratcompprio[j] * gdat.radistar
            xposlowr = xposmedi - gdat.stdvrratcompprio[j] * gdat.radistar
            xposuppr = xposmedi + gdat.stdvrratcompprio[j] * gdat.radistar
        xposlowr *= gdat.dictfact['rjre']
        xposuppr *= gdat.dictfact['rjre']
        axis.axvspan(xposlowr, xposuppr, alpha=0.5, color=gdat.listcolrcomp[j])
        axis.axvline(xposmedi, color=gdat.listcolrcomp[j], ls='--', label=gdat.liststrgcomp[j])
        axis.text(0.7, 0.9 - jj * 0.07, r'\textbf{%s}' % gdat.liststrgcomp[j], color=gdat.listcolrcomp[j], \
                                                                                    va='center', ha='center', transform=axis.transAxes)
    xerr = (timeoccu[1:] - timeoccu[:-1]) / 2.
    xerr = np.concatenate([xerr[0, None], xerr])
    axis.errorbar(timeoccu, occumean, yerr=occuyerr, xerr=xerr, color='black', ls='', marker='o', lw=1, zorder=10)
    axis.set_xlabel('Radius [$R_E$]')
    axis.set_ylabel('Occurrence rate of planets per star')
    plt.subplots_adjust(bottom=0.2)
    plt.subplots_adjust(left=0.2)
    path = pathimagfeatplan + 'occuradi_%s_%s.%s' % (gdat.strgtarg, strgpdfn, gdat.typefileplot)
    #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
    print('Writing to %s...' % path)
    plt.savefig(path)
    plt.close()
  
    # visualize the system
    path = pathimagfeatplan + 'orbt_%s_%s' % (gdat.strgtarg, strgpdfn)
    path = gdat.pathimagtarg + 'orbt'
    listtypevisu = ['real', 'cart']
    
    for typevisu in listtypevisu:
        
        if strgpdfn == 'post':
            radicomp = gdat.dicterrr['radicomp'][0, :]
            rsmacomp = gdat.dicterrr['rsmacomp'][0, :]
            epocmtracomp = gdat.dicterrr['epocmtracomp'][0, :]
            pericomp = gdat.dicterrr['pericomp'][0, :]
            cosicomp = gdat.dicterrr['cosicomp'][0, :]
        else:
            radicomp = gdat.radicompprio
            rsmacomp = gdat.rsmacompprio
            epocmtracomp = gdat.epocmtracompprio
            pericomp = gdat.pericompprio
            cosicomp = gdat.cosicompprio

        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                dictoutp = ephesus.retr_rflxtranmodl( \
                                                     gdat.arrytser['bdtr'][b][p][:, 0, 0], \
                                                     
                                                     radicomp=radicomp, \
                                                     rsmacomp=rsmacomp, \
                                                     epocmtracomp=epocmtracomp, \
                                                     pericomp=pericomp, \
                                                     cosicomp=cosicomp, \

                                                     typelmdk='quad', \
                                                     
                                                     typesyst=gdat.fitt.typemodl, \

                                                     typenorm='edgeleft', \

                                                     # plotting
                                                     pathfoldanim=pathfoldanim, \
                                                     typelang=typelang, \
                                                     typefileplot=typefileplot, \
                                                     
                                                     typevisu=typevisu, \

                                                     booldiag=booldiag, \

                                                     typeverb=1, \

                                                     boolintp=boolintp, \
                                                     
                                                     boolwritover=boolwritover, \
                                                     strgextn=strgextn, \
                                                     titlvisu=strgtitl, \

                                                     # sizefigr=gdat.figrsizeydob, \
                                                     # boolsingside=False, \
                                                     # boolanim=gdat.boolanimorbt, \
    
                                                    )
    
    for strgpopl in gdat.liststrgpopl:
        
        if strgpopl == 'exar':
            dictpopl = gdat.dictexar
        else:
            dictpopl = gdat.dictexof
        
        numbcomppopl = dictpopl['radicomp'].size
        indxtargpopl = np.arange(numbcomppopl)

        ### TSM and ESM
        numbsamppopl = 100
        dictlistplan = dict()
        for strgfeat in gdat.listfeatstarpopl:
            dictlistplan[strgfeat] = np.zeros((numbsamppopl, dictpopl['masscomp'].size)) + np.nan
            for k in range(dictpopl[strgfeat].size):
                meanvarb = dictpopl[strgfeat][k]
                if not np.isfinite(meanvarb):
                    continue
                if np.isfinite(dictpopl['stdv' + strgfeat][k]):
                    stdvvarb = dictpopl['stdv' + strgfeat][k]
                else:
                    stdvvarb = 0.
                
                dictlistplan[strgfeat][:, k] = tdpy.samp_gaustrun(numbsamppopl, meanvarb, stdvvarb, 0., np.inf)
                dictlistplan[strgfeat][:, k] /= np.mean(dictlistplan[strgfeat][:, k])
                dictlistplan[strgfeat][:, k] *= meanvarb
                
        #### TSM
        listtsmm = ephesus.retr_tsmm(dictlistplan['radicomp'], dictlistplan['tmptplan'], dictlistplan['masscomp'], \
                                                                                        dictlistplan['radistar'], dictlistplan['jmagsyst'])

        #### ESM
        listesmm = ephesus.retr_esmm(dictlistplan['tmptplan'], dictlistplan['tmptstar'], dictlistplan['radicomp'], dictlistplan['radistar'], \
                                                                                                                    dictlistplan['kmagsyst'])
        ## augment the 
        dictpopl['stdvtsmm'] = np.std(listtsmm, 0)
        dictpopl['tsmm'] = np.nanmedian(listtsmm, 0)
        dictpopl['stdvesmm'] = np.std(listesmm, 0)
        dictpopl['esmm'] = np.nanmedian(listesmm, 0)
        
        dictpopl['vesc'] = ephesus.retr_vesc(dictpopl['masscomp'], dictpopl['radicomp'])
        dictpopl['vesc0060'] = dictpopl['vesc'] / 6.
        
        objticrs = astropy.coordinates.SkyCoord(ra=dictpopl['rascstar']*astropy.units.degree, \
                                               dec=dictpopl['declstar']*astropy.units.degree, frame='icrs')
        
        # galactic longitude
        dictpopl['lgalstar'] = np.array([objticrs.galactic.l])[0, :]
        
        # galactic latitude
        dictpopl['bgalstar'] = np.array([objticrs.galactic.b])[0, :]
        
        # ecliptic longitude
        dictpopl['loecstar'] = np.array([objticrs.barycentricmeanecliptic.lon.degree])[0, :]
        
        # ecliptic latitude
        dictpopl['laecstar'] = np.array([objticrs.barycentricmeanecliptic.lat.degree])[0, :]

        dictpopl['stnomass'] = dictpopl['masscomp'] / dictpopl['stdvmasscomp']

        #dictpopl['boollive'] = ~dictpopl['boolfpos']
        dictpopl['boolterr'] = dictpopl['radicomp'] < 1.8
        dictpopl['boolhabicons'] = (dictpopl['inso'] < 1.01) & (dictpopl['inso'] > 0.35)
        dictpopl['boolhabiopti'] = (dictpopl['inso'] < 1.78) & (dictpopl['inso'] > 0.29)
        # unlocked
        dictpopl['boolunlo'] = np.log10(dictpopl['massstar']) < (-2 + 3 * (np.log10(dictpopl['smax']) + 1))
        # Earth as a transiting planet
        dictpopl['booleatp'] = abs(dictpopl['laecstar']) < 0.25

        ## Hill sphere
        ## angular momentum
    
        dictpopl['sage'] = 1. / 365.2422 / 24. / 3600. * (1. / 486.) * (0.008406 * dictpopl['smax'] / 0.027 / dictpopl['massstar']**(1. / 3.))**6
        dictpopl['timelock'] = (1. / 486.) * (dictpopl['smax'] / 0.027 / dictpopl['massstar']**(1. / 3.))**6

        #for strg in dictpopl.keys():
        #    print(strg)
        #    summgene(dictpopl[strg])
        #    print('')
        
        # from SETI
        dictpopl['metrplan'] = (0.99 * np.heaviside(dictpopl['numbplantranstar'] - 2, 1.) + 0.01)
        dictpopl['metrhzon'] = (0.99 * dictpopl['boolhabiopti'].astype(float) + 0.01)
        dictpopl['metrunlo'] = (0.99 * dictpopl['boolunlo'].astype(float) + 0.01)
        dictpopl['metrterr'] = (0.99 * dictpopl['boolterr'].astype(float) + 0.01)
        dictpopl['metrhabi'] = dictpopl['metrunlo'] * dictpopl['metrhzon'] * dictpopl['metrterr']
        dictpopl['metrseti'] = dictpopl['metrhabi'] * dictpopl['metrplan'] * dictpopl['distsyst']**(-2.)
        dictpopl['metrhzon'] /= np.nanmax(dictpopl['metrhzon'])
        dictpopl['metrhabi'] /= np.nanmax(dictpopl['metrhabi'])
        dictpopl['metrplan'] /= np.nanmax(dictpopl['metrplan'])
        dictpopl['metrseti'] /= np.nanmax(dictpopl['metrseti'])
        
        # period ratios
        ## all 
        gdat.listratiperi = []
        gdat.intgreso = []
        liststrgstarcomp = []
        for m in indxtargpopl:
            strgstar = dictpopl['namestar'][m]
            if not strgstar in liststrgstarcomp:
                indxexarstar = np.where(dictpopl['namestar'] == strgstar)[0]
                if indxexarstar[0] != m:
                    raise Exception('')
                
                listperi = dictpopl['pericomp'][None, indxexarstar]
                if not np.isfinite(listperi).all() or np.where(listperi == 0)[0].size > 0:
                    liststrgstarcomp.append(strgstar)
                    continue
                intgreso, ratiperi = ephesus.retr_reso(listperi)
                
                numbcomp = indxexarstar.size
                
                gdat.listratiperi.append(ratiperi[0, :, :][np.triu_indices(numbcomp, k=1)])
                gdat.intgreso.append(intgreso)
                
                liststrgstarcomp.append(strgstar)
        
        gdat.listratiperi = np.concatenate(gdat.listratiperi)
        figr, axis = plt.subplots(figsize=gdat.figrsize)
        bins = np.linspace(1., 10., 400)
        axis.hist(gdat.listratiperi, bins=bins, rwidth=1)
        if gdat.numbcomp > 1:
            ## this system
            for j in gmod.indxcomp:
                for jj in gmod.indxcomp:
                    if gdat.dicterrr['pericomp'][0, j] > gdat.dicterrr['pericomp'][0, jj]:
                        ratiperi = gdat.dicterrr['pericomp'][0, j] / gdat.dicterrr['pericomp'][0, jj]
                        axis.axvline(ratiperi, color=gdat.listcolrcomp[jj])
                        axis.axvline(ratiperi, color=gdat.listcolrcomp[j], ls='--')
        
        ylim = axis.get_ylim()
        ydatlabl = 0.9 * ylim[1] + ylim[0]
        ## resonances
        for perifrst, periseco in [[2., 1.], [3., 2.], [4., 3.], [5., 4.], [5., 3.], [5., 2.]]:
            rati = perifrst / periseco
            axis.text(rati + 0.05, ydatlabl, '%d:%d' % (perifrst, periseco), size=8, color='grey', va='center', ha='center')
            axis.axvline(perifrst / periseco, color='grey', ls='--', alpha=0.5)
        #axis.set_xscale('log')
        axis.set_xlim([0.9, 2.7])
        axis.set_ylabel('N')
        axis.set_xlabel('Period ratio')
        plt.subplots_adjust(bottom=0.2)
        plt.subplots_adjust(left=0.2)
        path = pathimagfeatplan + 'histratiperi_%s_%s_%s.%s' % (gdat.strgtarg, strgpdfn, strgpopl, gdat.typefileplot)
        #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
        print('Writing to %s...' % path)
        plt.savefig(path)
        plt.close()
        
        # metastable helium absorption
        path = gdat.pathbasemile + '/data/wasp107b_transmission_spectrum.dat'
        if gdat.typeverb > 0:
            print('Reading from %s...' % path)
        arry = np.loadtxt(path, delimiter=',', skiprows=1)
        wlenwasp0107 = arry[:, 0]
        deptwasp0107 = arry[:, 1]
        deptstdvwasp0107 = arry[:, 2]
        
        stdvnirs = 0.24e-2
        for a in range(2):
            duratranplanwasp0107 = 2.74
            jmagsystwasp0107 = 9.4
            if a == 1:
                radicomp = gdat.dicterrr['radicomp'][0, :]
                masscomp = gdat.dicterrr['masscompused'][0, :]
                tmptplan = gdat.dicterrr['tmptplan'][0, :]
                duratranplan = gdat.dicterrr['duratrantotl'][0, :]
                radistar = gdat.radistar
                jmagsyst = gdat.jmagsyst
            else:
                print('WASP-107')
                radicomp = 0.924 * gdat.dictfact['rjre']
                masscomp = 0.119
                tmptplan = 736
                radistar = 0.66 # [R_S]
                jmagsyst = jmagsystwasp0107
                duratranplan = duratranplanwasp0107
            scalheig = ephesus.retr_scalheig(tmptplan, masscomp, radicomp)
            deptscal = 1e3 * 2. * radicomp * scalheig / radistar**2 # [ppt]
            dept = 80. * deptscal
            factstdv = np.sqrt(10**((-jmagsystwasp0107 + jmagsyst) / 2.5) * duratranplanwasp0107 / duratranplan)
            stdvnirsthis = factstdv * stdvnirs
            for b in np.arange(1, 6):
                stdvnirsscal = stdvnirsthis / np.sqrt(float(b))
                sigm = dept / stdvnirsscal
        
            print('radicomp')
            print(radicomp)
            print('masscomp')
            print(masscomp)
            print('duratranplan')
            print(duratranplan)
            print('tmptplan')
            print(tmptplan)
            print('jmagsyst')
            print(jmagsyst)
            print('jmagsystwasp0107')
            print(jmagsystwasp0107)
            print('scalheig [R_E]')
            print(scalheig)
            print('scalheig [km]')
            print(scalheig * 71398)
            print('deptscal')
            print(deptscal)
            print('depttrancomp')
            print(dept)
            print('duratranplanwasp0107')
            print(duratranplanwasp0107)
            print('duratranplan')
            print(duratranplan)
            print('factstdv')
            print(factstdv)
            print('stdvnirsthis')
            print(stdvnirsthis)
            for b in np.arange(1, 6):
                print('With %d transits:' % b)
                print('stdvnirsscal')
                print(stdvnirsscal)
                print('sigm')
                print(sigm)
        print('James WASP107b scale height: 855 km')
        print('James WASP107b scale height: %g [R_E]' % (855. / 71398))
        print('James WASP107b depth per scale height: 5e-4')
        print('ampltide ratio fact: deptthis / 500e-6')
        fact = deptscal / 500e-6
        print('fact')
        print(fact)
        # 2 A * Rp * H / Rs**2
            
        figr, axis = plt.subplots(figsize=gdat.figrsize)
        #axis.errorbar(wlenwasp0107, deptwasp0107, yerr=deptstdvwasp0107, ls='', ms=1, lw=1, marker='o', color='k', alpha=1)
        axis.errorbar(wlenwasp0107-10833, deptwasp0107*fact[0], yerr=deptstdvwasp0107*factstdv[0], ls='', ms=1, lw=1, marker='o', color='k', alpha=1)
        axis.set_xlabel(r'Wavelength - 10,833 [$\AA$]')
        axis.set_ylabel('Depth [\%]')
        plt.subplots_adjust(bottom=0.2, left=0.2)
        path = pathimagdataplan + 'dept_%s_%s.%s' % (gdat.strgtarg, strgpdfn, gdat.typefileplot)
        #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
        print('Writing to %s...' % path)
        plt.savefig(path)
        plt.close()

        # optical magnitude vs number of planets
        for b in range(4):
            if b == 0:
                strgvarbmagt = 'vmag'
                lablxaxi = 'V Magnitude'
                varbtarg = gdat.vmagsyst
                varb = dictpopl['vmagsyst']
            if b == 1:
                strgvarbmagt = 'jmag'
                lablxaxi = 'J Magnitude'
                varbtarg = gdat.jmagsyst
                varb = dictpopl['jmagsyst']
            if b == 2:
                strgvarbmagt = 'rvelsemascal_vmag'
                lablxaxi = '$K^{\prime}_{V}$'
                varbtarg = np.sqrt(10**(-gdat.vmagsyst / 2.5)) / gdat.massstar**(2. / 3.)
                varb = np.sqrt(10**(-dictpopl['vmagsyst'] / 2.5)) / dictpopl['massstar']**(2. / 3.)
            if b == 3:
                strgvarbmagt = 'rvelsemascal_jmag'
                lablxaxi = '$K^{\prime}_{J}$'
                varbtarg = np.sqrt(10**(-gdat.vmagsyst / 2.5)) / gdat.massstar**(2. / 3.)
                varb = np.sqrt(10**(-dictpopl['jmagsyst'] / 2.5)) / dictpopl['massstar']**(2. / 3.)
            for a in range(2):
                figr, axis = plt.subplots(figsize=gdat.figrsize)
                if a == 0:
                    indx = np.where((dictpopl['numbplanstar'] > 3))[0]
                if a == 1:
                    indx = np.where((dictpopl['numbplantranstar'] > 3))[0]
                
                if (b == 2 or b == 3):
                    normfact = max(varbtarg, np.nanmax(varb[indx]))
                else:
                    normfact = 1.
                varbtargnorm = varbtarg / normfact
                varbnorm = varb[indx] / normfact
                axis.scatter(varbnorm, dictpopl['numbplanstar'][indx], s=1, color='black')
                
                indxsort = np.argsort(varbnorm)
                if b == 2 or b == 3:
                    indxsort = indxsort[::-1]

                listnameaddd = []
                cntr = 0
                maxmnumbname = min(5, varbnorm.size)
                while True:
                    k = indxsort[cntr]
                    nameadd = dictpopl['namestar'][indx][k]
                    if not nameadd in listnameaddd:
                        axis.text(varbnorm[k], dictpopl['numbplanstar'][indx][k] + 0.5, nameadd, size=6, \
                                                                                                va='center', ha='right', rotation=45)
                        listnameaddd.append(nameadd)
                    cntr += 1
                    if len(listnameaddd) == maxmnumbname: 
                        break
                axis.scatter(varbtargnorm, gdat.numbcomp, s=5, color='black', marker='x')
                axis.text(varbtargnorm, gdat.numbcomp + 0.5, gdat.labltarg, size=8, color='black', \
                                                                                            va='center', ha='center', rotation=45)
                axis.set_ylabel(r'Number of transiting planets')
                axis.set_xlabel(lablxaxi)
                plt.subplots_adjust(bottom=0.2)
                plt.subplots_adjust(left=0.2)
                path = pathimagfeatsyst + '%snumb_%s_%s_%s_%d.%s' % (strgvarbmagt, gdat.strgtarg, strgpdfn, strgpopl, a, gdat.typefileplot)
                #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                print('Writing to %s...' % path)
                plt.savefig(path)
                plt.close()

                figr, axis = plt.subplots(figsize=gdat.figrsize)
                axis.hist(varbnorm, 50)
                axis.axvline(varbtargnorm, color='black', ls='--')
                axis.text(0.3, 0.9, gdat.labltarg, size=8, color='black', transform=axis.transAxes, va='center', ha='center')
                axis.set_ylabel(r'Number of systems')
                axis.set_xlabel(lablxaxi)
                plt.subplots_adjust(bottom=0.2)
                plt.subplots_adjust(left=0.2)
                path = pathimagfeatsyst + 'hist_%s_%s_%s_%s_%d.%s' % (strgvarbmagt, gdat.strgtarg, strgpdfn, strgpopl, a, gdat.typefileplot)
                #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                print('Writing to %s...' % path)
                plt.savefig(path)
                plt.close()
            
        # planet feature distribution plots
        print('Will make the relevant distribution plots...')
        numbcomptext = min(10, numbcomppopl)
        liststrgtext = ['notx', 'text']
        
        # first is x-axis, second is y-axis
        liststrgfeatpairplot = [ \
                            #['smax', 'massstar'], \
                            #['rascstar', 'declstar'], \
                            #['lgalstar', 'bgalstar'], \
                            #['loecstar', 'laecstar'], \
                            #['distsyst', 'vmagsyst'], \
                            #['inso', 'radicomp'], \
                            ['radicomp', 'tmptplan'], \
                            ['radicomp', 'tsmm'], \
                            #['radicomp', 'esmm'], \
                            ['tmptplan', 'tsmm'], \
                            #['tagestar', 'vesc'], \
                            ['tmptplan', 'vesc0060'], \
                            #['radicomp', 'tsmm'], \
                            #['tmptplan', 'vesc'], \
                            #['pericomp', 'inso'], \
                            #['radistar', 'radicomp'], \
                            #['tmptplan', 'radistar'], \
                            #['projoblq', 'vsiistar'], \
                           ]
        
        numbpairfeatplot = len(liststrgfeatpairplot)

        indxpairfeatplot = np.arange(numbpairfeatplot)
        liststrgsort = ['none', \
                        #'esmm', \
                        'tsmm', \
                        #'metrhzon', 'metrhabi', 'metrplan', 'metrseti', \
                       ]
        numbstrgsort = len(liststrgsort)
        indxstrgsort = np.arange(numbstrgsort)

        indxcompfilt = dict()
        indxcompfilt['totl'] = indxtargpopl
        
        #indxcompfilt['tran'] = np.where(dictpopl['booltran'])[0]
        strgcuttmain = 'totl'
        
        #indxcompfilt['box1'] = np.where((dictpopl['radicomp'] < 3.5) & (dictpopl['radicomp'] > 3.) & (dictpopl['tmptplan'] > 300) & \
        #                                                                                            (dictpopl['tmptplan'] < 500) & dictpopl['booltran'])[0]
        #indxcompfilt['box2'] = np.where((dictpopl['radicomp'] < 2.5) & (dictpopl['radicomp'] > 2.) & (dictpopl['tmptplan'] > 800) & \
        #                                                                                            (dictpopl['tmptplan'] < 1000) & dictpopl['booltran'])[0]
        #indxcompfilt['box2'] = np.where((dictpopl['radicomp'] < 3.) & (dictpopl['radicomp'] > 2.5) & (dictpopl['tmptplan'] > 1000) & \
        #                                                                                            (dictpopl['tmptplan'] < 1400) & dictpopl['booltran'])[0]
        #indxcompfilt['box3'] = np.where((dictpopl['radicomp'] < 3.) & (dictpopl['radicomp'] > 2.5) & (dictpopl['tmptplan'] > 1000) & \
        #                                                                                            (dictpopl['tmptplan'] < 1400) & dictpopl['booltran'])[0]
        #indxcompfilt['r4tr'] = np.where((dictpopl['radicomp'] < 4) & dictpopl['booltran'])[0]
        #indxcompfilt['r4trtess'] = np.where((dictpopl['radicomp'] < 4) & dictpopl['booltran'] & \
        #                                                                (dictpopl['facidisc'] == 'Transiting Exoplanet Survey Satellite (TESS)'))[0]

        #indxcompfilt['r154'] = np.where((dictpopl['radicomp'] > 1.5) & (dictpopl['radicomp'] < 4))[0]
        #indxcompfilt['r204'] = np.where((dictpopl['radicomp'] > 2) & (dictpopl['radicomp'] < 4))[0]
        #indxcompfilt['rb24'] = np.where((dictpopl['radicomp'] < 4) & (dictpopl['radicomp'] > 2.))[0]
        #indxcompfilt['gmtr'] = np.where(np.isfinite(stnomass) & (stnomass > 5) & (dictpopl['booltran']))[0]
        #indxcompfilt['tran'] = np.where(dictpopl['booltran'])[0]
        #indxcompfilt['mult'] = np.where(dictpopl['numbplantranstar'] > 3)[0]
        #indxcompfilt['live'] = np.where(dictpopl['boollive'])[0]
        #indxcompfilt['terr'] = np.where(dictpopl['boolterr'] & dictpopl['boollive'])[0]
        #indxcompfilt['hzoncons'] = np.where(dictpopl['boolhabicons'] & dictpopl['boollive'])[0]
        #indxcompfilt['hzonopti'] = np.where(dictpopl['boolhabiopti'] & dictpopl['boollive'])[0]
        #indxcompfilt['unlo'] = np.where(dictpopl['boolunlo'] & dictpopl['boollive'])[0]
        #indxcompfilt['habi'] = np.where(dictpopl['boolterr'] & dictpopl['boolhabiopti'] & dictpopl['boolunlo'] & dictpopl['boollive'])[0]
        #indxcompfilt['eatp'] = np.where(dictpopl['booleatp'] & dictpopl['boollive'])[0]
        #indxcompfilt['seti'] = np.where(dictpopl['boolterr'] & dictpopl['boolhabicons'] & dictpopl['boolunlo'] & \
                                                                                            #dictpopl['booleatp'] & dictpopl['boollive'])[0]
        dicttemp = dict()
        dicttempmerg = dict()
        
        liststrgcutt = indxcompfilt.keys()
        
        liststrgvarb = [ \
                        'pericomp', 'inso', 'vesc0060', 'masscomp', \
                        'metrhzon', 'metrterr', 'metrplan', 'metrunlo', 'metrseti', \
                        'smax', \
                        'tmptstar', \
                        'rascstar', 'declstar', \
                        'loecstar', 'laecstar', \
                        'radistar', \
                        'massstar', \
                        'metastar', \
                        'radicomp', 'tmptplan', \
                        'metrhabi', 'metrplan', \
                        'lgalstar', 'bgalstar', 'distsyst', 'vmagsyst', \
                        'tsmm', 'esmm', \
                        'vsiistar', 'projoblq', \
                        'jmagsyst', \
                        'tagestar', \
                       ]

        listlablvarb, listscalpara = tdpy.retr_listlablscalpara(liststrgvarb)
        listlablvarbtotl = tdpy.retr_labltotl(listlablvarb)
        #listlablvarb = [ \
        #                ['P', 'days'], ['F', '$F_E$'], ['$v_{esc}^\prime$', 'kms$^{-1}$'], ['$M_p$', '$M_E$'], \
        #                [r'$\rho$_{HZ}', ''], [r'$\rho$_{T}', ''], [r'$\rho$_{MP}', ''], [r'$\rho$_{TL}', ''], [r'$\rho$_{SETI}', ''], \
        #                ['$a$', 'AU'], \
        #                ['$T_{eff}$', 'K'], \
        #                ['RA', 'deg'], ['Dec', 'deg'], \
        #                ['Ec. lon.', 'deg'], ['Ec. lat.', 'deg'], \
        #                ['$R_s$', '$R_S$'], \
        #                ['$M_s$', '$M_S$'], \
        #                ['[Fe/H]', 'dex'], \
        #                ['$R_p$', '$R_E$'], ['$T_p$', 'K'], \
        #                [r'$\rho_{SH}$', ''], [r'$\rho_{SP}$', ''], \
        #                ['$l$', 'deg'], ['$b$', 'deg'], ['$d$', 'pc'], ['$V$', ''], \
        #                ['TSM', ''], ['ESM', ''], \
        #                ['$v$sin$i$', 'kms$^{-1}$'], ['$\lambda$', 'deg'], \
        #                ['J', 'mag'], \
        #                ['$t_\star$', 'Gyr'], \
        #               ] 
        
        numbvarb = len(liststrgvarb)
        indxvarb = np.arange(numbvarb)
            
        # merge the target with the population
        for k, strgxaxi in enumerate(liststrgvarb + ['nameplan']):
            if not strgxaxi in dictpopl or not strgxaxi in gdat.dicterrr:
                continue
            dicttempmerg[strgxaxi] = np.concatenate([dictpopl[strgxaxi][indxcompfilt[strgcuttmain]], gdat.dicterrr[strgxaxi][0, :]])
        
        if not 'nameplan' in dictpopl:
            raise Exception('')

        #if not 'nameplan' in gdat.dicterrr:
        #    raise Exception('')

        if not 'nameplan' in dicttempmerg:
            raise Exception('')

        for k, strgxaxi in enumerate(liststrgvarb):
            
            if strgxaxi == 'tmptplan':
                print('strgxaxi in dictpopl')
                print(strgxaxi in dictpopl)
                print('strgxaxi in gdat.dicterrr')
                print(strgxaxi in gdat.dicterrr)
                raise Exception('')

            if not strgxaxi in dictpopl:
                continue

            if not strgxaxi in gdat.dicterrr:
                continue

            if not 'tmptplan' in dicttempmerg:
                print('dicttempmerg')
                print(dicttempmerg.keys())
                raise Exception('')

            for m, strgyaxi in enumerate(liststrgvarb):
                
                booltemp = False
                for l in indxpairfeatplot:
                    if strgxaxi == liststrgfeatpairplot[l][0] and strgyaxi == liststrgfeatpairplot[l][1]:
                        booltemp = True
                if not booltemp:
                    continue
                 
                # to be deleted
                #for strgfeat, valu in dictpopl.items():
                    #dicttempmerg[strgfeat] = np.concatenate([dictpopl[strgfeat][indxcompfilt[strgcuttmain]], gdat.dicterrr[strgfeat][0, :]])
                
                for strgcutt in liststrgcutt:
                    
                    # merge population with the target
                    #for strgfeat, valu in dictpopl.items():
                    #    dicttemp[strgfeat] = np.concatenate([dictpopl[strgfeat][indxcompfilt[strgcutt]], gdat.dicterrr[strgfeat][0, :]])
                    
                    liststrgfeatcsvv = [ \
                                        #'inso', 'metrhzon', 'radicomp', 'metrterr', 'massstar', 'smax', 'metrunlo', 'distsyst', 'metrplan', 'metrseti', \
                                        'rascstar', 'declstar', 'radicomp', 'masscomp', 'tmptplan', 'jmagsyst', 'radistar', 'tsmm', \
                                       ]
                    for y in indxstrgsort:
                        
                        if liststrgsort[y] != 'none':
                        
                            indxgood = np.where(np.isfinite(dicttempmerg[liststrgsort[y]]))[0]
                            indxsort = np.argsort(dicttempmerg[liststrgsort[y]][indxgood])[::-1]
                            indxcompsort = indxgood[indxsort]
                            
                            path = gdat.pathdatatarg + '%s_%s_%s.csv' % (strgpopl, strgcutt, liststrgsort[y])
                            objtfile = open(path, 'w')
                            
                            strghead = '%4s, %20s' % ('Rank', 'Name')
                            for strgfeatcsvv in liststrgfeatcsvv:
                                strghead += ', %12s' % listlablvarbtotl[liststrgvarb.index(strgfeatcsvv)]
                            strghead += '\n'
                            
                            objtfile.write(strghead)
                            cntr = 1
                            for l in indxcompsort:
                                
                                strgline = '%4d, %20s' % (cntr, dicttempmerg['nameplan'][l])
                                for strgfeatcsvv in liststrgfeatcsvv:
                                    strgline += ', %12.4g' % dicttempmerg[strgfeatcsvv][l]
                                strgline += '\n'
                                
                                objtfile.write(strgline)
                                cntr += 1 
                            print('Writing to %s...' % path)
                            objtfile.close()
                    
                        if gdat.boolplotpopl:
                            # repeat, one without text, one with text
                            for b, strgtext in enumerate(liststrgtext):
                                figr, axis = plt.subplots(figsize=gdat.figrsize)
                                
                                if liststrgsort[y] != 'none' and strgtext != 'text' or liststrgsort[y] == 'none' and strgtext == 'text':
                                    continue
                        
                                ## population
                                if strgcutt == strgcuttmain:
                                    axis.errorbar(dicttempmerg[strgxaxi], dicttempmerg[strgyaxi], ls='', ms=1, marker='o', color='k')
                                else:
                                    axis.errorbar(dicttempmerg[strgxaxi], dicttempmerg[strgyaxi], ls='', ms=1, marker='o', color='k')
                                    #axis.errorbar(dicttemp[strgxaxi], dicttemp[strgyaxi], ls='', ms=2, marker='o', color='r')
                                
                                ## this system
                                for j in gmod.indxcomp:
                                    if strgxaxi in gdat.dicterrr:
                                        xdat = gdat.dicterrr[strgxaxi][0, j, None]
                                        xerr = gdat.dicterrr[strgxaxi][1:3, j, None]
                                    if strgyaxi in gdat.dicterrr:
                                        ydat = gdat.dicterrr[strgyaxi][0, j, None]
                                        yerr = gdat.dicterrr[strgyaxi][1:3, j, None]
                                    
                                    # temp apply cut on this system
                                    
                                    if strgxaxi in gdat.listfeatstar and strgyaxi in gdat.listfeatstar:
                                        axis.errorbar(xdat, ydat, color='k', lw=1, xerr=xerr, yerr=yerr, ls='', marker='o', ms=6, zorder=2)
                                        axis.text(0.85, 0.9 - j * 0.08, gdat.labltarg, color='k', \
                                                                                              va='center', ha='center', transform=axis.transAxes)
                                        break
                                    else:
                                        
                                        if not strgxaxi in gdat.dicterrr and strgyaxi in gdat.dicterrr:
                                            if strgyaxi in gdat.listfeatstar:
                                                axis.axhline(ydat, color='k', lw=1, ls='--', zorder=2)
                                                axis.text(0.85, 0.9 - j * 0.08, gdat.labltarg, color='k', \
                                                                                              va='center', ha='center', transform=axis.transAxes)
                                                break
                                            else:
                                                axis.axhline(ydat, color=gdat.listcolrcomp[j], lw=1, ls='--', zorder=2)
                                        if not strgyaxi in gdat.dicterrr and strgxaxi in gdat.dicterrr:
                                            if strgxaxi in gdat.listfeatstar:
                                                axis.axvline(xdat, color='k', lw=1, ls='--', zorder=2)
                                                axis.text(0.85, 0.9 - j * 0.08, gdat.labltarg, color='k', \
                                                                                              va='center', ha='center', transform=axis.transAxes)
                                                break
                                            else:
                                                axis.axvline(xdat, color=gdat.listcolrcomp[j], lw=1, ls='--')
                                        if strgxaxi in gdat.dicterrr and strgyaxi in gdat.dicterrr:
                                            axis.errorbar(xdat, ydat, color=gdat.listcolrcomp[j], lw=1, xerr=xerr, yerr=yerr, ls='', marker='o', \
                                                                                                                                zorder=2, ms=6)
                                        
                                        if strgxaxi in gdat.dicterrr or strgyaxi in gdat.dicterrr:
                                            axis.text(0.85, 0.9 - j * 0.08, r'\textbf{%s}' % gdat.liststrgcomp[j], color=gdat.listcolrcomp[j], \
                                                                                            va='center', ha='center', transform=axis.transAxes)
                                
                                # include text
                                if liststrgsort[y] != 'none' and strgtext == 'text':
                                    for ll, l in enumerate(indxcompsort):
                                        if ll < numbcomptext:
                                            text = '%s' % dicttemp['nameplan'][l]
                                            xdat = dicttemp[strgxaxi][l]
                                            ydat = dicttemp[strgyaxi][l]
                                            if np.isfinite(xdat) and np.isfinite(ydat):
                                                objttext = axis.text(xdat, ydat, text, size=1, ha='center', va='center')
                                
                                if strgxaxi == 'tmptplan' and strgyaxi == 'vesc0060':
                                    xlim = [0, 0]
                                    xlim[0] = 0.5 * np.nanmin(dictpopl['tmptplan'])
                                    xlim[1] = 2. * np.nanmax(dictpopl['tmptplan'])
                                    arrytmptplan = np.linspace(xlim[0], xlim[1], 1000)
                                    cons = [1., 4., 16., 18., 28., 44.] # H, He, CH4, H20, CO, CO2
                                    for i in range(len(cons)):
                                        arryyaxi = (arrytmptplan / 40. / cons[i])**0.5
                                        axis.plot(arrytmptplan, arryyaxi, color='grey', alpha=0.5)
                                    axis.set_xlim(xlim)

                                if strgxaxi == 'radicomp' and strgyaxi == 'masscomp':
                                    gdat.listlabldenscomp = ['Earth-like', 'Pure Water', 'Pure Iron']
                                    listdenscomp = [1., 0.1813, 1.428]
                                    listposicomp = [[13., 2.6], [4.7, 3.5], [13., 1.9]]
                                    gdat.numbdenscomp = len(gdat.listlabldenscomp)
                                    gdat.indxdenscomp = np.arange(gdat.numbdenscomp)
                                    masscompdens = np.linspace(0.5, 16.) # M_E
                                    for i in gdat.indxdenscomp:
                                        radicompdens = (masscompdens / listdenscomp[i])**(1. / 3.)
                                        axis.plot(masscompdens, radicompdens, color='grey')
                                    for i in gdat.indxdenscomp:
                                        axis.text(listposicomp[i][0], listposicomp[i][1], gdat.listlabldenscomp[i])
                                
                                #if strgxaxi == 'tmptplan':
                                #    axis.axvline(273., ls='--', alpha=0.3, color='k')
                                #    axis.axvline(373., ls='--', alpha=0.3, color='k')
                                #if strgyaxi == 'tmptplan':
                                #    axis.axhline(273., ls='--', alpha=0.3, color='k')
                                #    axis.axhline(373., ls='--', alpha=0.3, color='k')
        
                                axis.set_xlabel(listlablvarbtotl[k])
                                axis.set_ylabel(listlablvarbtotl[m])
                                if listscalpara[k] == 'logt':
                                    axis.set_xscale('log')
                                if listscalpara[m] == 'logt':
                                    axis.set_yscale('log')
                                
                                plt.subplots_adjust(left=0.2)
                                plt.subplots_adjust(bottom=0.2)
                                pathimagfeatplan = getattr(gdat, 'pathimagfeatplan' + strgpdfn)
                                path = pathimagfeatplan + 'feat_%s_%s_%s_%s_%s_%s_%s_%s.%s' % \
                                             (strgxaxi, strgyaxi, gdat.strgtarg, strgpopl, strgcutt, \
                                                                                   strgtext, liststrgsort[y], strgpdfn, gdat.typefileplot)
                                #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.5, 0.1]})
                                print('Writing to %s...' % path)
                                plt.savefig(path)
                                plt.close()

   
def bdtr_wrap(gdat, b, p, y, epocmask, perimask, duramask, strgintp, strgoutp, strgtren, timescalbdtrspln):
    '''
    Wrap baseline-detrending function of ephesus for miletos
    '''
    
    # output
    gdat.listarrytser[strgoutp][b][p][y] = np.copy(gdat.listarrytser[strgintp][b][p][y])
    
    # trend
    gdat.listarrytser[strgtren][b][p][y] = np.copy(gdat.listarrytser[strgintp][b][p][y])
    
    for e in gdat.indxener:
        gdat.rflxbdtrregi, gdat.listindxtimeregi[b][p][y], gdat.indxtimeregioutt[b][p][y], gdat.listobjtspln[b][p][y], gdat.listtimebrek = \
                     ephesus.bdtr_tser(gdat.listarrytser[strgintp][b][p][y][:, e, 0], gdat.listarrytser[strgintp][b][p][y][:, e, 1], \
                                                stdvlcur=gdat.listarrytser[strgintp][b][p][y][:, e, 2], \
                                                epocmask=epocmask, perimask=perimask, duramask=duramask, \
                                                timescalbdtrspln=timescalbdtrspln, \
                                                typeverb=gdat.typeverb, \
                                                timeedge=gdat.listtimebrek, \
                                                timebrekregi=gdat.timebrekregi, \
                                                ordrspln=gdat.ordrspln, \
                                                timescalbdtrmedi=gdat.timescalbdtrmedi, \
                                                boolbrekregi=gdat.boolbrekregi, \
                                                typebdtr=gdat.typebdtr, \
                                                )
    
        gdat.listarrytser[strgoutp][b][p][y][:, e, 1] = np.concatenate(gdat.rflxbdtrregi)
    
    numbsplnregi = len(gdat.rflxbdtrregi)
    gdat.indxsplnregi[b][p][y] = np.arange(numbsplnregi)


def plot_tsercore(gdat, strgarry, b, p, y=None, boolcolrtran=True):
    
    boolchun = y is not None
    
    if not boolchun and gdat.numbchun[b][p] == 1:
        return
        
    if boolchun:
        arrytser = gdat.listarrytser[strgarry][b][p][y]
    else:
        arrytser = gdat.arrytser[strgarry][b][p]
    
    # determine name of the file
    ## string indicating the prior on the transit ephemerides
    strgprioplan = ''
    if strgarry != 'raww' and gdat.typepriocomp is not None:
        strgprioplan = '_%s' % gdat.typepriocomp
    strgcolr = ''
    if boolcolrtran:
        strgcolr = '_colr'
    strgchun = ''
    if boolchun:
        strgchun = '_' + gdat.liststrgchun[b][p][y]
    path = gdat.pathimagtarg + '%s%s_%s%s_%s%s_%s%s.%s' % \
                    (gdat.liststrgtser[b], gdat.strgcnfg, strgarry, strgcolr, gdat.liststrginst[b][p], strgchun, gdat.strgtarg, strgprioplan, gdat.typefileplot)
    
    if not strgarry.startswith('bdtroutpit') and not strgarry.startswith('clipoutpit'):
        if strgarry == 'raww':
            limt = [0., 0.9, 0.5, 0.1]
        elif strgarry == 'bdtr':
            limt = [0., 0.7, 0.5, 0.1]
        else:
            limt = [0., 0.5, 0.5, 0.1]
        gdat.listdictdvrp[0].append({'path': path, 'limt':limt})
        
    if not os.path.exists(path):
            
        figr, axis = plt.subplots(figsize=gdat.figrsizeydobskin)
        
        if arrytser.shape[1] > 1:
            extent = [gdat.listener[0], gdat.listener[1], arrytser[0, 0, 0] - gdat.timeoffs, arrytser[-1, 0, 0] - gdat.timeoffs]
            imag = axis.imshow(arrytser[:, :, 1].T, extent=extent)
        else:
            axis.plot(arrytser[:, 0, 0] - gdat.timeoffs, arrytser[:, 0, 1], color='grey', marker='.', ls='', ms=1, rasterized=True)
        
        if boolcolrtran:
            # color and name transits
            ylim = axis.get_ylim()
            listtimetext = []
            for j in gmod.indxcomp:
                if boolchun:
                    indxtime = gdat.listindxtimetranchun[j][b][p][y] 
                else:
                    if y > 0:
                        continue
                    indxtime = gdat.listindxtimetran[j][b][p][0]
                
                colr = gdat.listcolrcomp[j]
                # plot data
                axis.plot(arrytser[indxtime, 0] - gdat.timeoffs, arrytser[indxtime, 1], color=colr, marker='.', ls='', ms=1, rasterized=True)
                # draw planet names
                for n in np.linspace(-gdat.numbcyclcolrplot, gdat.numbcyclcolrplot, 2 * gdat.numbcyclcolrplot + 1):
                    time = gdat.epocmtracompprio[j] + n * gdat.pericompprio[j] - gdat.timeoffs
                    if np.where(abs(arrytser[:, 0] - gdat.timeoffs - time) < 0.1)[0].size > 0:
                        
                        # add a vertical offset if overlapping
                        if np.where(abs(np.array(listtimetext) - time) < 0.5)[0].size > 0:
                            ypostemp = ylim[0] + (ylim[1] - ylim[0]) * 0.95
                        else:
                            ypostemp = ylim[0] + (ylim[1] - ylim[0]) * 0.9

                        # draw the planet letter
                        axis.text(time, ypostemp, r'\textbf{%s}' % gdat.liststrgcomp[j], color=gdat.listcolrcomp[j], va='center', ha='center')
                        listtimetext.append(time)
        
        if boolchun:
            if strgarry == 'flar':
                ydat = axis.get_ylim()[1]
                for kk in range(len(gdat.listindxtimeflar[p][y])):
                    ms = 0.5 * gdat.listmdetflar[p][y][kk]
                    axis.plot(arrytser[gdat.listindxtimeflar[p][y][kk], 0] - gdat.timeoffs, ydat, marker='v', color='b', ms=ms, rasterized=True)
                axis.plot(arrytsertren[:, 0] - gdat.timeoffs, arrytsertren[:, 1], color='g', marker='.', ls='', ms=1, rasterized=True)
                axis.fill_between(arrytsertren[:, 0] - gdat.timeoffs, arrytsertren[:, 1] - gdat.thrsrflxflar[p][y] + 1., \
                                                                      arrytsertren[:, 1] + gdat.thrsrflxflar[p][y] - 1., \
                                                                      color='c', alpha=0.2, rasterized=True)
                
            if strgarry == 'flarprep':
                axis.axhline(gdat.thrsrflxflar[p][y], ls='--', alpha=0.5, color='r')
            
        axis.set_xlabel('Time [BJD - %d]' % gdat.timeoffs)
        if arrytser.shape[1] > 1:
            axis.set_ylabel(gdat.lablener)
            cbar = plt.colorbar(imag)
        else:
            axis.set_ylabel(gdat.listlabltser[b])
        axis.set_title(gdat.labltarg)
        plt.subplots_adjust(bottom=0.2)
        
        if gdat.typeverb > 0:
            print('Writing to %s...' % path)
        plt.savefig(path, dpi=200)
        plt.close()
    

    if gdat.numbener > 1:
        # plot each energy
        
        path = gdat.pathimagtarg + '%s%s_%s%s_%s%s_%s%s_ener.%s' % \
                    (gdat.liststrgtser[b], gdat.strgcnfg, strgarry, strgcolr, gdat.liststrginst[b][p], strgchun, gdat.strgtarg, strgprioplan, gdat.typefileplot)
    
        if not os.path.exists(path):
                
            figr, axis = plt.subplots(figsize=gdat.figrsizeydobskin)
            
            sprdrflx = np.amax(np.std(arrytser[:, :, 1], 0)) * 5.
            listdiffrflxener = np.linspace(-1., 1., gdat.numbener) * 0.5 * gdat.numbener * sprdrflx

            for e in gdat.indxener:
                color = plt.cm.rainbow(e / (gdat.numbener - 1))
                axis.plot(arrytser[:, e, 0] - gdat.timeoffs, arrytser[:, e, 1] + listdiffrflxener[e], color=color, marker='.', ls='', ms=1, rasterized=True)
            
            if boolcolrtran:
                # color and name transits
                ylim = axis.get_ylim()
                listtimetext = []
                for j in gmod.indxcomp:
                    if boolchun:
                        indxtime = gdat.listindxtimetranchun[j][b][p][y] 
                    else:
                        if y > 0:
                            continue
                        indxtime = gdat.listindxtimetran[j][b][p][0]
                    
                    colr = gdat.listcolrcomp[j]
                    # plot data
                    axis.plot(arrytser[indxtime, 0] - gdat.timeoffs, arrytser[indxtime, 1], color=colr, marker='.', ls='', ms=1, rasterized=True)
                    # draw planet names
                    for n in np.linspace(-gdat.numbcyclcolrplot, gdat.numbcyclcolrplot, 2 * gdat.numbcyclcolrplot + 1):
                        time = gdat.epocmtracompprio[j] + n * gdat.pericompprio[j] - gdat.timeoffs
                        if np.where(abs(arrytser[:, 0] - gdat.timeoffs - time) < 0.1)[0].size > 0:
                            
                            # add a vertical offset if overlapping
                            if np.where(abs(np.array(listtimetext) - time) < 0.5)[0].size > 0:
                                ypostemp = ylim[0] + (ylim[1] - ylim[0]) * 0.95
                            else:
                                ypostemp = ylim[0] + (ylim[1] - ylim[0]) * 0.9

                            # draw the planet letter
                            axis.text(time, ypostemp, r'\textbf{%s}' % gdat.liststrgcomp[j], color=gdat.listcolrcomp[j], va='center', ha='center')
                            listtimetext.append(time)
            
            if boolchun:
                if strgarry == 'flar':
                    ydat = axis.get_ylim()[1]
                    for kk in range(len(gdat.listindxtimeflar[p][y])):
                        ms = 0.5 * gdat.listmdetflar[p][y][kk]
                        axis.plot(arrytser[gdat.listindxtimeflar[p][y][kk], 0] - gdat.timeoffs, ydat, marker='v', color='b', ms=ms, rasterized=True)
                    axis.plot(arrytsertren[:, 0] - gdat.timeoffs, arrytsertren[:, 1], color='g', marker='.', ls='', ms=1, rasterized=True)
                    axis.fill_between(arrytsertren[:, 0] - gdat.timeoffs, arrytsertren[:, 1] - gdat.thrsrflxflar[p][y] + 1., \
                                                                          arrytsertren[:, 1] + gdat.thrsrflxflar[p][y] - 1., \
                                                                          color='c', alpha=0.2, rasterized=True)
                    
                if strgarry == 'flarprep':
                    axis.axhline(gdat.thrsrflxflar[p][y], ls='--', alpha=0.5, color='r')
                
            axis.set_xlabel('Time [BJD - %d]' % gdat.timeoffs)
            axis.set_ylabel(gdat.listlabltser[b])
            axis.set_title(gdat.labltarg)
            plt.subplots_adjust(bottom=0.2)
            
            if gdat.typeverb > 0:
                print('Writing to %s...' % path)
            plt.savefig(path, dpi=200)
            plt.close()


def plot_tser(gdat, b, p, y, strgarry, booltoge=True):
    
    # plot each chunck
    plot_tsercore(gdat, strgarry, b, p, y, boolcolrtran=False)
    
    # plot all chunks together if there is more than one chunk
    if y == 0 and gdat.numbchun[b][p] > 1 and booltoge:
        plot_tsercore(gdat, strgarry, b, p, boolcolrtran=False)
    
    # highlight times in-transit
    if gdat.numbcomp is not None:
        
        ## plot each chunck
        plot_tsercore(gdat, strgarry, b, p, y, boolcolrtran=True)
        
        ## plot all chunks together if there is more than one chunk
        if y == 0 and gdat.numbchun[b][p] > 1:
            plot_tsercore(gdat, strgarry, b, p, boolcolrtran=True)

        if b == 0:
            path = gdat.pathimagtarg + 'rflx%s_intr%s_%s_%s_%s.%s' % \
                                            (strgarry, gdat.strgcnfg, gdat.liststrginst[b][p], gdat.strgtarg, gdat.typepriocomp, gdat.typefileplot)
            if not os.path.exists(path):
                # plot only the in-transit data
                figr, axis = plt.subplots(gdat.numbcomp, 1, figsize=gdat.figrsizeydobskin, sharex=True)
                if gdat.numbcomp == 1:
                    axis = [axis]
                for jj, j in enumerate(gmod.indxcomp):
                    axis[jj].plot(gdat.arrytser[strgarry][b][p][gdat.listindxtimetran[j][b][p][0], 0] - gdat.timeoffs, \
                                                                         gdat.arrytser[strgarry][b][p][gdat.listindxtimetran[j][b][p][0], 1], \
                                                                                           color=gdat.listcolrcomp[j], marker='o', ls='', ms=0.2)
                
                axis[-1].set_ylabel(gdat.labltserphot)
                #axis[-1].yaxis.set_label_coords(0, gdat.numbcomp * 0.5)
                axis[-1].set_xlabel('Time [BJD - %d]' % gdat.timeoffs)
                
                #plt.subplots_adjust(bottom=0.2)
                #gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.8, 0.8]})
                print('Writing to %s...' % path)
                plt.savefig(path)
                plt.close()
        

def plot_tser_bdtr(gdat, b, p, y, z, r, strgarryinpt, strgarryoutp):
    '''
    Plot baseline detrending.
    '''
    
    ## string indicating the prior on the transit ephemerides
    strgprioplan = ''
    
    #if strgarry != 'raww' and gdat.typepriocomp is not None:
    #    strgprioplan = '_%s' % gdat.typepriocomp
    
    path = gdat.pathimagtarg + 'rflx_ts%02dit%02dsumm%s_%s_%s_%s%s%s.%s' % (z, r, gdat.strgcnfg, gdat.liststrginst[b][p], \
                                        gdat.liststrgchun[b][p][y], gdat.strgtarg, strgprioplan, gdat.liststrgener[gdat.indxenerclip], gdat.typefileplot)
    gdat.listdictdvrp[0].append({'path': path, 'limt':[0., 0.05, 1.0, 0.2]})
    if not os.path.exists(path):
            
        figr, axis = plt.subplots(2, 1, figsize=gdat.figrsizeydob)
        for i in gdat.indxsplnregi[b][p][y]:
            ## non-baseline-detrended light curve
            axis[0].plot(gdat.listarrytser[strgarryinpt][b][p][y][:, gdat.indxenerclip, 0] - gdat.timeoffs, \
                         gdat.listarrytser[strgarryinpt][b][p][y][:, gdat.indxenerclip, 1], rasterized=True, alpha=gdat.alphraww, \
                                                                                            marker='o', ls='', ms=1, color='grey')
            ## spline
            if gdat.listobjtspln[b][p][y] is not None and gdat.listobjtspln[b][p][y][i] is not None:
                minmtimeregi = gdat.listarrytser[strgarryinpt][b][p][y][0, gdat.indxenerclip, 0]
                maxmtimeregi = gdat.listarrytser[strgarryinpt][b][p][y][-1, gdat.indxenerclip, 0]
                timesplnregifine = np.linspace(minmtimeregi, maxmtimeregi, 1000)
                if gdat.typebdtr == 'spln':
                    lcurtren = gdat.listobjtspln[b][p][y][i](timesplnregifine)
                if gdat.typebdtr == 'gpro':
                    lcurtren = gdat.listobjtspln[b][p][y][i].predict(gdat.listarrytser[strgarryinpt][b][p][y][gdat.indxtimeregioutt[b][p][y][i], gdat.indxenerclip, 1], \
                                                                                                                        t=timesplnregifine, return_cov=False, return_var=False)
                axis[0].plot(timesplnregifine - gdat.timeoffs, lcurtren, 'b-', lw=3, rasterized=True)
            ## baseline-detrended light curve
            axis[1].plot(gdat.listarrytser[strgarryoutp][b][p][y][:, gdat.indxenerclip, 0] - gdat.timeoffs, \
                         gdat.listarrytser[strgarryoutp][b][p][y][:, gdat.indxenerclip, 1], rasterized=True, alpha=gdat.alphraww, \
                                                                                              marker='o', ms=1, ls='', color='grey')
        for a in range(2):
            axis[a].set_ylabel(gdat.labltserphot)
        axis[0].set_xticklabels([])
        axis[1].set_xlabel('Time [BJD - %d]' % gdat.timeoffs)
        plt.subplots_adjust(hspace=0.)
        print('Writing to %s...' % path)
        plt.savefig(path, dpi=200)
        plt.close()
                            

def retr_namebdtrclip(e, r):

    strgarrybdtrinpt = 'ts%02dit%02dbdtrinpt' % (e, r)
    strgarryclipinpt = 'ts%02dit%02dclipinpt' % (e, r)
    strgarryclipoutp = 'ts%02dit%02dclipoutp' % (e, r)
    strgarrybdtrblin = 'ts%02dit%02dbdtrblin' % (e, r)
    strgarrybdtroutp = 'ts%02dit%02dbdtroutp' % (e, r)

    return strgarrybdtrinpt, strgarryclipoutp, strgarrybdtroutp, strgarryclipinpt, strgarrybdtrblin


def setp_para(gdat, strgmodl, nameparabase, minmpara, maxmpara, lablpara, strgener=None, strgcomp=None, strglmdk=None):
    
    gmod = getattr(gdat, strgmodl)
    
    nameparabasefinl = nameparabase
    
    if strgcomp is not None:
        nameparabasefinl += strgcomp

    if strglmdk is not None:
        nameparabasefinl += strglmdk

    if strgener is not None:
        nameparabasefinl += strgener

    if hasattr(gmod, nameparabasefinl):
        if gdat.typeverb > 0:
            print('%s has been fixed to %g...' % (nameparabasefinl, getattr(gmod, nameparabasefinl)))
    else:
        gmod.listnamepara += [nameparabasefinl]
        gdat.dictindxpara[nameparabasefinl] = gdat.cntr
        gdat.listlablpara.append(lablpara)
        gdat.listminmpara.append(minmpara)
        gdat.listmaxmpara.append(maxmpara)
        gdat.dictfeatpara['scal'].append('self')
        
        if strgener is not None:
            if gdat.typemodlener == 'full':
                intg = int(strgener[-2:])
            else:
                intg = 0
        
        if strgcomp is not None and strgener is not None:
            if gdat.typemodlener == 'full':
                gdat.dictindxpara[nameparabase + 'compener'][int(strgcomp[-1]), intg] = gdat.cntr
            else:
                gdat.dictindxpara[nameparabase + 'compener'][int(strgcomp[-1]), 0] = gdat.cntr
        elif strglmdk is not None and strgener is not None:
            if strglmdk == 'linr':
                intglmdk = 0
            if strglmdk == 'quad':
                intglmdk = 1
            gdat.dictindxpara[nameparabase + 'ener'][intglmdk, intg] = gdat.cntr
        elif strgener is not None:
            gdat.dictindxpara[nameparabase + 'ener'][intg] = gdat.cntr
        elif strgcomp is not None:
            gdat.dictindxpara[nameparabase + 'comp'][int(strgcomp[-1])] = gdat.cntr
        
        gdat.cntr += 1
    gmod.listnameparafull += [nameparabasefinl]
    

def proc_modl(gdat, strgextn, ee, e):
    
    gdat.fitt.listnameparafullfixd = []
    gdat.fitt.listnameparafullflot = []
    for name in gdat.fitt.listnameparafull:
        if hasattr(gdat.fitt, name):
            gdat.fitt.listnameparafullfixd.append(name)
        else:
            gdat.fitt.listnameparafullflot.append(name)
    
    if gdat.booldiag:
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                if len(gdat.arrytser['bdtr'][b][p]) == 0:
                    print('')
                    print('')
                    print('')
                    print('bp')
                    print(bp)
                    raise Exception('')
        
    #gdat.timethis = gdat.arrytser['bdtr'][b][p][:, 0, 0]
    #gdat.rflxthis = gdat.arrytser['bdtr'][b][p][:, :, 1]
    #gdat.stdvrflxthis = gdat.arrytser['bdtr'][b][p][:, :, 2]
    #gdat.varirflxthis = gdat.stdvrflxthis**2


    
    gdat.listminmpara = np.array(gdat.listminmpara)
    gdat.listmaxmpara = np.array(gdat.listmaxmpara)

    gdat.listlablpara, _, _, _, _ = tdpy.retr_listlablscalpara(gdat.fitt.listnamepara, gdat.listlablpara, booldiag=gdat.booldiag)
    gdat.listlablparatotl = tdpy.retr_labltotl(gdat.listlablpara)
    
    gdat.numbpara = len(gdat.fitt.listnamepara)
    gdat.meanpara = np.empty(gdat.numbpara)
    gdat.stdvpara = np.empty(gdat.numbpara)
    
    gdat.bfitperi = 4.25 # [days]
    gdat.stdvperi = 1e-2 * gdat.bfitperi # [days]
    gdat.bfitduratran = 0.45 * 24. # [hours]
    gdat.stdvduratran = 1e-1 * gdat.bfitduratran # [hours]
    gdat.bfitamplslen = 0.14 # [relative]
    gdat.stdvamplslen = 1e-1 * gdat.bfitamplslen # [relative]
    
    #gdat.listlablpara = [['$R_s$', 'R$_{\odot}$'], ['$P$', 'days'], ['$M_c$', 'M$_{\odot}$'], ['$M_s$', 'M$_{\odot}$']]
    #gdat.listlablparaderi = [['$A$', ''], ['$D$', 'hours'], ['$a$', 'R$_{\odot}$'], ['$R_{Sch}$', 'R$_{\odot}$']]
    #gdat.listlablpara += [['$M$', '$M_E$'], ['$T_{0}$', 'BJD'], ['$P$', 'days']]
    #gdat.listminmpara = np.concatenate([gdat.listminmpara, np.array([ 10., minmtime,  50.])])
    #gdat.listmaxmpara = np.concatenate([gdat.listmaxmpara, np.array([1e4, maxmtime, 200.])])
    
    meangauspara = None
    stdvgauspara = None
    numbpara = len(gdat.listlablpara)
    indxpara = np.arange(numbpara)
    
    listscalpara = gdat.dictfeatpara['scal']

    # run the sampler
    if gdat.typeinfe == 'samp':
        gdat.dictsamp = tdpy.samp(gdat, \
                             gdat.numbsampwalk, \
                             retr_llik_mile, \
                             gdat.fitt.listnamepara, gdat.listlablpara, listscalpara, gdat.listminmpara, gdat.listmaxmpara, \
                             pathbase=gdat.pathtargruns, \
                             retr_dictderi=retr_dictderi_mile, \
                             numbsampburnwalk=gdat.numbsampburnwalk, \
                             strgextn=strgextn, \
                             typeverb=gdat.typeverb, \
                             boolplot=gdat.boolplot, \
                            )
    
    if gdat.typeinfe == 'opti':
        
        bounds = [[] for kk in range(gdat.listminmpara.size)]
        print('bounds')
        for kk in range(gdat.listminmpara.size):
            bounds[kk] = [gdat.listminmpara[kk], gdat.listmaxmpara[kk]]
            print('%s %s: %g %g' % (gdat.fitt.listnamepara[kk], gdat.listlablpara[kk], gdat.listminmpara[kk], gdat.listmaxmpara[kk]))
        print('')
            
        indx = np.where(gdat.liststrgeneritermlikdone == gdat.liststrgeneriter[gdat.indxdataiterthis[0]])[0]
        if indx.size == 1:
            print('Reading from the stored solution...')
            paramlik = gdat.datamlik[indx[0]][np.arange(0, 2 * gdat.listminmpara.size - 1, 2)]
            stdvmlik = gdat.datamlik[indx[0]][np.arange(0, 2 * gdat.listminmpara.size - 1, 2) + 1]
        else:

            gdat.parainit = gdat.listminmpara + 0.5 * (gdat.listmaxmpara - gdat.listminmpara)
            
            print('gdat.parainit')
            for kk in range(gdat.listminmpara.size):
                print('%s %s: %g' % (gdat.fitt.listnamepara[kk], gdat.listlablpara[kk], gdat.parainit[kk]))
            print('')
            
            print('Maximizing the likelihood...')
            # minimize the negative loglikelihood
            objtmini = scipy.optimize.minimize(retr_lliknega_mile, gdat.parainit, \
                                                                            method='Nelder-Mead', \
                                                                            #method='BFGS', \
                                                                            #method='L-BFGS-B', \
                                                                            #ftol=0.1, \
                                                                            options={ \
                                                                            #"initial_simplex": simplex,
                                                                                        "disp": True, \
                                                                                        "maxiter" : gdat.parainit.size*200,
                                                                                        "fatol": 0.2, \
                                                                                        "adaptive": True, \
                                                                                        }, \
                                                                                          bounds=bounds, args=(gdat))
            
            paramlik = objtmini.x
            print('objtmini.success')
            print(objtmini.success)
            print(objtmini.status)
            print(objtmini.message)
            #print(objtmini.hess)
            print()
            gdat.indxpara = np.arange(paramlik.size)
            #stdvmlik = objtmini.hess_inv[gdat.indxpara, gdat.indxpara]
            stdvmlik = np.empty_like(paramlik)
            deltpara = 1e-6
            for kk in gdat.indxpara:
                paranewwfrst = np.copy(paramlik)
                paranewwfrst[kk] = (1 - deltpara) * paranewwfrst[kk]
                paranewwseco = np.copy(paramlik)
                paranewwseco[kk] = (1 + deltpara) * paranewwseco[kk]
                stdvmlik[kk] = 1. / np.sqrt(abs(retr_lliknega_mile(paranewwfrst, gdat) + retr_lliknega_mile(paranewwseco, gdat) \
                                                                             - 2. * retr_lliknega_mile(paramlik, gdat)) / (deltpara * paramlik[kk])**2)

            path = gdat.pathdatatarg + 'paramlik.csv'
            if gdat.typeverb > 0:
                print('Writing to %s...' % path)
            objtfile = open(path, 'a+')
            objtfile.write('%s' % gdat.liststrgeneriter[gdat.indxdataiterthis[0]])
            for kk, paramliktemp in enumerate(paramlik):
                objtfile.write(', %g, %g' % (paramliktemp, stdvmlik[kk]))
            objtfile.write('\n')
            objtfile.close()
        
        print('paramlik')
        for kk in range(gdat.listminmpara.size):
            print('%s %s: %g +- %g' % (gdat.fitt.listnamepara[kk], gdat.listlablpara[kk], paramlik[kk], stdvmlik[kk]))
        
        gdat.dictmlik = dict()
        for kk in range(gdat.listminmpara.size):
            gdat.dictmlik[gdat.fitt.listnamepara[kk]] = paramlik[kk]
            gdat.dictmlik['stdv' + gdat.fitt.listnamepara[kk]] = stdvmlik[kk]
        print('Computing derived variables...')
        dictderimlik = retr_dictderi_mile(paramlik, gdat)
        for name in dictderimlik:
            gdat.dictmlik[name] = dictderimlik[name]
                
    if gdat.typemodlener == 'iter' or gdat.numbener == 1:
        if gdat.typeinfe == 'samp':
            gdat.listdictsamp.append(gdat.dictsamp)
        if gdat.typeinfe == 'opti':
            gdat.listdictmlik.append(gdat.dictmlik)

    if gdat.boolplottser:
        if ee < 10:
        
            #timedata = gdat.timethisfitt
            #lcurdata = gdat.rflxthisfitt[:, ee]
                
            for b in gdat.indxdatatser:
                plot_modl(gdat, b, None, None, ee, e)
                for p in gdat.indxinst[b]:
                    plot_modl(gdat, b, p, None, ee, e)
                    for y in gdat.indxchun[b][p]:
                        plot_modl(gdat, b, p, y, ee, e)


def plot_modl(gdat, b, p, y, ee, e):
            
    # plot the data with the posterior median model
    strgextn = 'pmed%s%s' % (gdat.strgcnfg, gdat.liststrgeneriter[ee])
    dictmodl = dict()
    for namecompmodl in gdat.fitt.listnamecompmodl:
        namecompmodlextn = 'rflxmodl' + namecompmodl + 'fine'
        if gdat.typeinfe == 'samp':
            if gdat.typemodlener == 'full':
                lcurtemp = np.median(gdat.dictsamp[namecompmodlextn][:, :, ee], 0)
            else:
                lcurtemp = np.median(gdat.listdictsamp[ee][namecompmodlextn][:, :, 0], 0)
            strgtitl = 'Posterior median model'
        else:
            if gdat.typemodlener == 'full':
                lcurtemp = gdat.dictmlik[namecompmodlextn][:, ee]
            else:
                lcurtemp = gdat.listdictmlik[ee][namecompmodlextn][:, 0]
        if namecompmodl == 'totl':
            colr = 'b'
            labl = 'Total Model'
        elif namecompmodl == 'base':
            colr = 'g'
            labl = 'Baseline'
        elif namecompmodl == 'tran':
            colr = 'r'
            labl = 'Transit'
        elif namecompmodl == 'supn':
            colr = 'r'
            labl = 'Supernova'
        elif namecompmodl == 'excs':
            colr = 'orange'
            labl = 'Excess'
        else:
            raise Exception('')
        dictmodl['pmed' + namecompmodlextn] = {'lcur': lcurtemp, 'time': gdat.timethisfittfine, 'labl': labl, 'colr': colr}
    
    if p is not None:
        strglablinst = ', %s' % gdat.listlablinst[b][p]
    else:
        strglablinst = ''

    if ee == 0 and gdat.numbener == 1:
        strgtitl = '%s%s' % (gdat.labltarg, strglablinst)
    elif ee == 0 and gdat.numbener > 1:
        strgtitl = '%s%s, white' % (gdat.labltarg, strglablinst)
    else:
        strgtitl = '%s%s, %g micron' % (gdat.labltarg, strglablinst, gdat.listener[ee-1])
    
    pathplot = ephesus.plot_lcur(gdat.pathimagtarg, \
                                 timedata=gdat.timethisfitt, \
                                 lcurdata=gdat.rflxthisfitt, \
                                 timeoffs=gdat.timeoffs, \
                                 strgextn=strgextn, \
                                 strgtitl=strgtitl, \
                                 boolwritover=gdat.boolwritover, \
                                 boolbrekmodl=gdat.boolbrekmodl, \
                                 dictmodl=dictmodl)
    
    # plot the posterior median residual
    strgextn = 'resipmed%s%s' % (gdat.strgcnfg, gdat.liststrgeneriter[ee])
    dictmodl = dict()
    if gdat.typeinfe == 'samp':
        if gdat.typemodlener == 'full':
            lcurdatatemp = np.median(gdat.dictsamp['rflxresi'][:, :, e], 0)
        else:
            lcurdatatemp = np.median(gdat.listdictsamp[ee]['rflxresi'][:, :, 0], 0)
    else:
        if gdat.typemodlener == 'full':
            lcurdatatemp = gdat.dictmlik['rflxresi'][:, e]
        else:
            lcurdatatemp = gdat.listdictmlik[ee]['rflxresi'][:, 0]
    pathplot = ephesus.plot_lcur(gdat.pathimagtarg, \
                                 timedata=gdat.timethisfitt, \
                                 lcurdata=lcurdatatemp, \
                                 timeoffs=gdat.timeoffs, \
                                 strgextn=strgextn, \
                                 strgtitl=strgtitl, \
                                 lablyaxi='Residual relative flux', \
                                 boolwritover=gdat.boolwritover, \
                                 boolbrekmodl=gdat.boolbrekmodl, \
                                )
    
    # plot the data with a number of total model samples
    if gdat.typeinfe == 'samp':
        strgextn = 'psam%s' % gdat.strgcnfg
        if gdat.numbener > 1:
            strgextn += gdat.liststrgeneriter[ee]
        dictmodl = dict()
        for w in range(gdat.numbsampplot):
            namevarbsamp = 'psammodl%04d' % w
            if gdat.typemodlener == 'full':
                dictmodl[namevarbsamp] = {'lcur': gdat.dictsamp['rflxmodltotlfine'][w, :, e], 'time': gdat.timethisfittfine}
            else:
                dictmodl[namevarbsamp] = {'lcur': gdat.listdictsamp[ee]['rflxmodltotlfine'][w, :, 0], 'time': gdat.timethisfittfine}
            if w == 0:
                dictmodl[namevarbsamp]['labl'] = 'Model'
            else:
                dictmodl[namevarbsamp]['labl'] = None
            dictmodl[namevarbsamp]['colr'] = 'b'
            dictmodl[namevarbsamp]['alph'] = 0.2
        pathplot = ephesus.plot_lcur(gdat.pathimagtarg, \
                                     timedata=gdat.timethisfitt, \
                                     lcurdata=gdat.rflxthisfitt, \
                                     timeoffs=gdat.timeoffs, \
                                     strgextn=strgextn, \
                                     boolwritover=gdat.boolwritover, \
                                     strgtitl=strgtitl, \
                                     boolbrekmodl=gdat.boolbrekmodl, \
                                     dictmodl=dictmodl)

        # plot the data with a number of model component samples
        strgextn = 'psamcomp%s' % gdat.strgcnfg
        if gdat.numbener > 1:
            strgextn += gdat.liststrgeneriter[ee]
        dictmodl = dict()
        for namecompmodl in gdat.fitt.listnamecompmodl:
            if namecompmodl == 'totl':
                continue

            if namecompmodl == 'totl':
                colr = 'b'
                labl = 'Total Model'
            elif namecompmodl == 'base':
                colr = 'g'
                labl = 'Baseline'
            elif namecompmodl == 'supn':
                colr = 'r'
                labl = 'Supernova'
            elif namecompmodl == 'excs':
                colr = 'orange'
                labl = 'Excess'
            else:
                raise Exception('')
            for w in range(gdat.numbsampplot):
                namevarbsamp = 'psam%s%04d' % (namecompmodl, w)
                if gdat.typemodlener == 'full':
                    dictmodl[namevarbsamp] = {'lcur': gdat.dictsamp['rflxmodl%sfine' % namecompmodl][w, :, e], 'time': gdat.timethisfittfine}
                else:
                    dictmodl[namevarbsamp] = \
                                {'lcur': gdat.listdictsamp[ee]['rflxmodl%sfine' % namecompmodl][w, :, 0], 'time': gdat.timethisfittfine}
                if w == 0:
                    dictmodl[namevarbsamp]['labl'] = labl
                else:
                    dictmodl[namevarbsamp]['labl'] = None
                dictmodl[namevarbsamp]['colr'] = colr
                dictmodl[namevarbsamp]['alph'] = 0.6
        pathplot = ephesus.plot_lcur(gdat.pathimagtarg, \
                                     timedata=timedata, \
                                     timeoffs=gdat.timeoffs, lcurdata=lcurdata, strgextn=strgextn, \
                                     boolwritover=gdat.boolwritover, \
                                     strgtitl=strgtitl, \
                                     boolbrekmodl=gdat.boolbrekmodl, \
                                     dictmodl=dictmodl)

    # plot the binned RMS
    path = gdat.pathimagtarg + 'stdvrebn%s%s.%s' % (gdat.strgcnfg, gdat.liststrgeneriter[ee], gdat.typefileplot)
    if not os.path.exists(path):
        if gdat.typeinfe == 'samp':
            if gdat.typemodlener == 'full':
                stdvrflxresi = np.median(gdat.dictsamp['stdvrflxresi'][:, :, e], 0)
            else:
                stdvrflxresi = np.median(gdat.listdictsamp[ee]['stdvrflxresi'][:, :, 0], 0)
        else:
            if gdat.typemodlener == 'full':
                stdvrflxresi = gdat.dictmlik['stdvrflxresi'][:, e]
            else:
                stdvrflxresi = gdat.listdictmlik[ee]['stdvrflxresi'][:, 0]
    
        figr, axis = plt.subplots(figsize=gdat.figrsizeydob)
        axis.loglog(gdat.listdeltrebn[b][p] * 24., stdvrflxresi * 1e6, ls='', marker='o', ms=1, label='Binned Std. Dev')
        axis.axvline(gdat.ratesamptime[b][p] * 24., ls='--', label='Sampling rate')
        axis.set_ylabel('RMS [ppm]')
        axis.set_xlabel('Bin width [hour]')
        axis.legend()
        plt.tight_layout()
        if gdat.typeverb > 0:
            print('Writing to %s...' % path)
        plt.savefig(path)
        plt.close()
        








def setp_para_defa(gdat, strgmodl, strgvarb, valuvarb):
    
    gmod = getattr(gdat, strgmodl)
    
    if strgmodl == 'fitt':
        dicttemp = gdat.dictfitt
    if strgmodl == 'true':
        dicttemp = gdat.dicttrue

    if strgvarb in dicttemp:
        valuvarbdefa = dicttemp[strgvarb]
    else:
        valuvarbdefa = valuvarb
    
    setattr(gmod, strgvarb, valuvarbdefa)


def init_modl(gdat):
    
    gdat.dictindxpara = dict()
    gdat.dictfeatpara = dict()
    gdat.dictfeatpara['scal'] = []
    
    gdat.listlablpara = []
    gdat.listminmpara = []
    gdat.listmaxmpara = []
    gdat.fitt.listnamepara = []
    gdat.fitt.listnameparafull = []
            
    # counter for the parameter index
    gdat.cntr = 0


def setp_modlbase(gdat, strgmodl, e, ee):
    
    gmod = getattr(gdat, strgmodl)
    
    # type of baseline offset
    setp_para_defa(gdat, strgmodl, 'typemodlbase', 'cons')
    
    gdat.listnamecompgpro = ['totl']
    if gmod.typemodlbase == 'gpro':
        gdat.listnamecompgpro.append('base')
    
    gmod.listnamecompmodl = ['base']
    if gmod.typemodl == 'supn':
        gmod.listnamecompmodl += ['supn']
        if gmod.typemodlexcs != 'none':
            gmod.listnamecompmodl += ['excs']
    
    if gmod.typemodl == 'psys':
        gmod.listnamecompmodl += ['tran']
    
    if len(gmod.listnamecompmodl) > 1:
        gmod.listnamecompmodl += ['totl']

    if gmod.typemodlbase == 'gpro':
        gmod.listnameparabase = ['sigmgprobase', 'rhoogprobase']
    if gmod.typemodlbase == 'cons':
        gmod.listnameparabase = ['cons']
    if gmod.typemodlbase == 'step':
        gmod.listnameparabase = ['consfrst', 'consseco', 'timestep', 'scalstep']
    for nameparabase in gmod.listnameparabase:
        gdat.dictindxpara[nameparabase + 'ener'] = np.empty(gdat.numbenerthismodl, dtype=int)
        if nameparabase.startswith('sigmgprobase'):
            minmpara = 0.01 # [ppt]
            maxmpara = 4. # [ppt]
            lablpara = ['$\sigma_{GP}$', '']
        if nameparabase.startswith('rhoogprobase'):
            minmpara = 1e-3
            maxmpara = 0.3
            lablpara = [r'$\rho_{GP}$', '']
        if nameparabase.startswith('cons'):
            if nameparabase == 'consfrst':
                lablpara = ['$C_1$', 'ppt']
                minmpara = -20. # [ppt]
                maxmpara = 20. # [ppt]
            elif nameparabase == 'consseco':
                lablpara = ['$C_2$', 'ppt']
                minmpara = -20. # [ppt]
                maxmpara = -4. # [ppt]
            else:
                lablpara = ['$C$', 'ppt']
                minmpara = -20. # [ppt]
                maxmpara = 20. # [ppt]
        if nameparabase.startswith('timestep'):
            minmpara = 791.11
            maxmpara = 791.13
            lablpara = '$T_s$'
        if nameparabase.startswith('scalstep'):
            minmpara = 0.0001
            maxmpara = 0.002
            lablpara = '$A_s$'

        if gdat.numbener > 1 and gdat.typemodlener == 'full':
            for e in gdat.indxener:
                setp_para(gdat, strgmodl, nameparabasefinl, minmpara, maxmpara, lablpara, strgener=gdat.liststrgener[e])
        else:
            setp_para(gdat, strgmodl, nameparabase, minmpara, maxmpara, lablpara, strgener=gdat.liststrgeneriter[ee])
   
    if ee > 0:
        setattr(gmod, 'timestep' + gdat.liststrgeneriter[ee], 791.12)
    
    if ee > 0:
        setattr(gmod, 'scalstep' + gdat.liststrgeneriter[ee], 0.00125147)
                        
    # list of companion parameter names
    gmod.listnameparacomp = []
    
    if gmod.typemodl == 'psysttvr':
        if gdat.typefittttvr == 'lineindi' and ll == 0 or gdat.typefittttvr == 'glob' or gdat.typefittttvr == 'globfull':
            gmod.listnameparacomp += ['peri', 'epocmtra']
        if gdat.typefittttvr == 'glob':
            for lll in range(numbiterfitt):
                gmod.listnameparacomp += ['ttvr%04d' % lll]
        else:
            gmod.listnameparacomp += ['ttvr%04d' % ll]
    
    if gmod.typemodl == 'psys' or gmod.typemodl == 'cosc' or gmod.typemodl == 'psysttvr' and gdat.typefittttvr == 'globfull':
        gmod.listnameparacomp += ['rsma', 'peri', 'epocmtra', 'cosi']
    if gmod.typemodl == 'psys' or gmod.typemodl == 'psysttvr' and gdat.typefittttvr == 'globfull':
        gmod.listnameparacomp += ['rrat']
    if gmod.typemodl == 'cosc':
        gmod.listnameparacomp += ['mass']
    
    # define arrays of parameter indices for companions
    for namepara in gmod.listnameparacomp:
        gdat.dictindxpara[namepara + 'comp'] = np.empty(gdat.numbcomp, dtype=int)

    if 'rratcomp' in gmod.listnameparacomp:
        if gdat.numbener > 1 and gdat.typemodlener == 'full':
            gdat.dictindxpara['rratcompener'] = np.empty((gdat.numbcomp, gdat.numbener), dtype=int)
        else:
            gdat.dictindxpara['rratcompener'] = np.empty((gdat.numbcomp, 1), dtype=int)
    
    # limb darkening
    if gmod.typemodl == 'psys' or gmod.typemodl == 'cosc':
        if gdat.typemodllmdkterm != 'none':
            if gdat.typemodllmdkener == 'ener' and gdat.typemodlener == 'full':
                gdat.dictindxpara['coeflmdkener'] = np.empty((gdat.numbcoeflmdkterm, gdat.numbcoeflmdkener), dtype=int)
            else:
                gdat.dictindxpara['coeflmdkener'] = np.empty((gdat.numbcoeflmdkterm, 1), dtype=int)
        
            #gdat.listnamevarbsyst += ['coeflmdkener']
                
            #gdat.dictindxpara['coeflmdklinrener'] = np.empty(1, dtype=int)
            #gdat.dictindxpara['coeflmdkquadener'] = np.empty(1, dtype=int)
            
            if gdat.numbener > 1 and gdat.typemodlener == 'full':
                for e in gdat.indxener:
                    #setattr(gmod, 'coeflmdklinr' + gdat.liststrgener[e], 0.2)
                    #setattr(gmod, 'coeflmdkquad' + gdat.liststrgener[e], 0.4)
                    setp_para(gdat, strgmodl, '', minmpara, maxmpara, None, strgener=gdat.liststrgener[e], strglmdk=strglmdk)
            else:

                if gdat.typemodllmdkener == 'cons' or gdat.typemodllmdkener == 'ener':
                    
                    strgener = gdat.liststrgeneriter[ee]
                    
                    if gdat.typemodllmdkterm != 'none':
                        #if ee > 0:
                        #    setattr(gmod, 'coeflmdklinr' + gdat.liststrgeneriter[ee], 0.4)
                        # add linear coefficient
                        setp_para(gdat, strgmodl, 'coeflmdk', 0., 0.15, None, strglmdk='linr', strgener=strgener)
                        
                    if gdat.typemodllmdkterm == 'quad':
                        #if ee > 0:
                        #    setattr(gmod, 'coeflmdkquad' + gdat.liststrgeneriter[ee], 0.25)
                        setp_para(gdat, strgmodl, 'coeflmdk', 0., 0.3, None, strglmdk='quad', strgener=strgener)
                        
                elif gdat.typemodllmdkener == 'line':
                    if gdat.typemodllmdkterm != 'none':
                        setp_para(gdat, strgmodl, 'ratecoeflmdklinr', 0., 1., None)
                    
                    if gdat.typemodllmdkterm == 'quad':
                        setp_para(gdat, strgmodl, 'ratecoeflmdkquad', 0., 1., None)
                else:
                    raise Exception('')

        for j in gmod.indxcomp:
            
            # define parameter limits
            if gmod.typemodl == 'cosc':
                setp_para(gdat, strgmodl, 'radistar', 0.1, 100., ['$R_*$', ''])
                setp_para(gdat, strgmodl, 'massstar', 0.1, 100., ['$M_*$', ''])
            
            strgcomp = 'com%d' % j
            
            if 'rsma' in gmod.listnameparacomp:
                setp_para(gdat, strgmodl, 'rsma', 0.06, 0.14, None, strgcomp=strgcomp)
            
            if 'peri' in gmod.listnameparacomp:
                setp_para(gdat, strgmodl, 'peri', gdat.pericompprio[j] - 0.01 * gdat.pericompprio[j], \
                                                    gdat.pericompprio[j] + 0.01 * gdat.pericompprio[j], None, strgcomp=strgcomp)
            
            if 'epocmtra' in gmod.listnameparacomp:
                setp_para(gdat, strgmodl, 'epocmtra', 791.10, 791.13, None, strgcomp=strgcomp)
            
            if 'cosi' in gmod.listnameparacomp:
                setp_para(gdat, strgmodl, 'cosi', 0., 0.08, None, strgcomp=strgcomp)
            
            if 'rrat' in gmod.listnameparacomp:
                minmpara = 0.11
                maxmpara = 0.19
                if gdat.numbener > 1 and gdat.typemodlener == 'full':
                    for e in gdat.indxener:
                        setp_para(gdat, strgmodl, 'rrat', minmpara, maxmpara, None, strgener=gdat.liststrgener[e], strgcomp=strgcomp)
                else:
                    setp_para(gdat, strgmodl, 'rrat', minmpara, maxmpara, None, strgener=gdat.liststrgeneriter[ee], strgcomp=strgcomp)
                
            if gmod.typemodl == 'cosc':
                setp_para(gdat, strgmodl, 'mass', 0.1, 100., ['$M_c$', ''], strgcomp=strgcomp)

    if gmod.typemodl == 'supn':
        # temp
        if gdat.liststrgtypedata[0][0].startswith('simu'):
            minmtimesupn = gdat.minmtimethis + 0.15 * (gdat.maxmtimethis - gdat.minmtimethis) - gdat.timeoffs
            maxmtimesupn = gdat.minmtimethis + 0.35 * (gdat.maxmtimethis - gdat.minmtimethis) - gdat.timeoffs
        else:
            minmtimesupn = 358.
            maxmtimesupn = 363.
        
        lablpara = ['$T_0$', 'BJD-%d' % gdat.timeoffs]
        setp_para(gdat, strgmodl, 'timesupn', minmtimesupn, maxmtimesupn, lablpara)
        
        if gdat.fitt.typemodlexcs == 'bump':
            setp_para(gdat, strgmodl, 'timebumpoffs', 0., 1., ['$T_b$', ''])
            setp_para(gdat, strgmodl, 'amplbump', 0., 50., [r'$A_b$', '']) # [ppt]
            setp_para(gdat, strgmodl, 'scalbump', 0.01, 0.5, [r'$u_b$', ''])
        
        setp_para(gdat, strgmodl, 'coeflinesupn', -20., 50., ['$c_1$', 'ppt'])
        if gdat.fitt.typemodlsupn == 'quad':
            setp_para(gdat, strgmodl, 'coefquadsupn', -20., 50., ['$c_2$', 'ppt'])


def init( \
         
         # a string distinguishing the run
         strgcnfg=None, \
         
         # target identifiers
         ## string to search on MAST
         strgmast=None, \
         
         ## TIC ID
         ticitarg=None, \
         
         ## TOI ID
         toiitarg=None, \
         
         ## RA
         rasctarg=None, \
         
         ## Dec
         decltarg=None, \

         ## a string for the label of the target
         labltarg=None, \
         
         ## a string for the folder name and file name extensions
         strgtarg=None, \
         
         # string indicating the cluster of targets
         strgclus=None, \
        
         ## Boolean flag indicating whether the input photometric data will be median-normalized
         boolnormphot=True, \

         
         # options changing the overall execution
         ## Boolean flag to enforce offline operation
         boolforcoffl=False, \

         ## Boolean flag to search for and analyze time-domain data on the target
         booltserdata=True, \
        
         
         # target visibility from a given observatory over a given night and year
         ## Boolean flag to calculate visibility of the target
         boolcalcvisi=False, \
         
         ## Boolean flag to plot visibility of the target
         boolplotvisi=None, \
         
         ## latitude of the observatory for the visibility calculation
         latiobvt=None, \
         
         ## longitude of the observatory for the visibility calculation
         longobvt=None, \
         
         ## height of the observatory for the visibility calculation
         heigobvt=None, \
         
         ## string of time for the night
         strgtimeobvtnigh=None, \
         
         ## string of time for the beginning of the year
         strgtimeobvtyear=None, \
         
         ## list of time difference samples for the year
         listdelttimeobvtyear=None, \
         
         ## local time offset for the visibility calculation
         offstimeobvt=0., \
            
         # dictionary for parameters of the true generative model
         dicttrue=dict(), \

         # dictionary for parameters of the fitting generative model
         dictfitt=dict(), \

         ## general plotting
         ## Boolean flag to make plots
         boolplot=True, \
         
         ## Boolean flag to plot target features along with the features of the parent population
         boolplotpopl=False, \
         
         ## Boolean flag to plot DV reports
         boolplotdvrp=None, \
         
         ## Boolean flag to plot the time-series
         boolplottser=None, \
         
         ## Boolean flag to animate the orbit
         boolanimorbt=False, \
         
         ## time offset to subtract from the time axes, which is otherwise automatically estimated
         timeoffs=None, \
         
         ## file type of the plot
         typefileplot='png', \

         ## Boolean flag to write planet name on plots
         boolwritplan=True, \
         
         ## Boolean flag to rasterize the raw time-series on plots
         boolrastraww=True, \
         
         ## list of transit depths to indicate on the light curve and phase curve plots
         listdeptdraw=None, \
         
         
         # paths
         ## the path of the folder in which the target folder will be placed
         pathbase=None, \
         
         ## the path of the target folder
         pathtarg=None, \
         
         ## the path of the target data folder
         pathdatatarg=None, \
         
         ## the path of the target image folder
         pathimagtarg=None, \
         
         # data
         ## string indicating the type of data

         ## path of the CSV file containing the input data
         listpathdatainpt=None, \
         
         ## input data as a dictionary of lists of numpy arrays
         listarrytser=None, \
         
         ## list of TESS sectors for the input data
         listtsec=None, \
         
         ## list of values for the energy axis
         listener=None, \
         
         ## label for the energy axis
         lablener=None, \
         
         ## type of inference over energy axis to perform inference using
         ### 'full': all energy bins simultaneously
         ### 'iter': iterate over energy bins
         typemodlener=None, \
         
         # type of data for each data kind, instrument, and chunk
         liststrgtypedata=None, \

         ## list of labels indicating instruments
         listlablinst=None, \
         
         ## list of strings indicating instruments
         liststrginst=None, \
         
         ## list of strings indicating chunks
         liststrgchun=None, \
         
         ## list of chunk indices for each instrument
         listindxchuninst=None, \
         
         ## input dictionary for lygos                                
         dictlygoinpt=None, \
         
         
         ## Boolean flag to mask bad data
         dictlcurtessinpt=None, \
         
         ## time limits to mask
         listlimttimemask=None, \
        
         ## type of pipeline to fit TTVs
         ### 'userindi': TTV fit for each transit separately with linear ephemeris fixed to that from the user
         ### 'lineindi': a linear ephemeris fit followed by TTV fit for each transit separately with linear ephemeris fixed to that from the former
         ### 'glob': TTV fit across all transits along with a free linear ephemeris
         ### 'globfull': TTV fit across all transits along with a free transit model
         typefittttvr=None, \

         # analyses
         ## list of types of analyses for time series data
         listtypeanls=None, \
         
         ## transit search
         ### input dictionary to the search pipeline for periodic boxes
         dictpboxinpt=None, \
        
         ### input dictionary to the search pipeline for single transits
         dictsrchtransinginpt=None, \
         
         ## flare search
         ### threshold percentile for detecting stellar flares
         thrssigmflar=7., \

         ### input dictionary to the search pipeline for flares
         dictsrchflarinpt=dict(), \
        
         # fitting
         # Boolean flag to reject the lowest log-likelihood during log-likelihood calculation
         boolrejeoutlllik=False, \

         # model
         # type of inference
         ## 'samp': sample from the posterior
         ## 'opti': optimize the likelihood
         typeinfe='samp', \

         # list of types of models for time series data
         ## 'psys': gravitationally bound system of a star and potentially transiting planets
         ## 'psysphas': gravitationally bound system of a star and potentially transiting planets with phase modulations
         ## 'ssys': gravitationally bound system of potentially transiting two stars
         ## 'cosc': gravitationally bound system of a star and potentially transiting compact companion
         ## 'flar': stellar flare
         ## 'agns': AGN
         ## 'spot': stellar spot
         ## 'supn': supernova
         ## 'stargpro': star with variability described by a Gaussian Process
         listtypemodl=None, \

         # stellar limb darkening
         ## a string indicating how limb darkening coefficients change across energies
         ### 'cons': constant at all energies
         ### 'line': linear change across energies
         ### 'ener': free at all energies
         typemodllmdkener='cons', \
         ## a string indicating how limb darkening coefficients change across energies
         ### 'cons': constant at all angles
         ### 'line': linear in the cosine of the angle between the observer and the surface normal (i.e., gamma)
         ### 'quad': quadratic in the cosine of the angle between the observer and the surface normal (i.e., gamma)
         typemodllmdkterm='quad', \
         
         # limits of time between which the fit is performed
         limttimefitt=None, \

         ## flare model
         ### type of model for finding flares
         typemodlflar='outl', \

         ## transit model
         ## dilution: None (no correction), 'lygos' for estimation via lygos, or float value
         dilu=None, \
         
         ## priors
         ### Boolean flag to detrend the photometric time-series before estimating the priors
         boolbdtr=None, \
         ### baseline detrending
         #### minimum time interval for breaking the time-series into regions, which will be detrended separately
         timebrekregi=0.1, \
         #### Boolean flag to break the time-series into regions
         boolbrekregi=False, \

         #### type of the baseline model
         typebdtr='gpro', \
         #### order of the spline
         ordrspln=3, \
         #### time scale for median-filtering detrending
         timescalbdtrmedi=2., \
         #### time scale for spline baseline detrending
         listtimescalbdtrspln=[2.], \

         ### maximum frequency (per day) for LS periodogram
         maxmfreqlspe=None, \
         
         # threshold BLS SDE for disposing the target as positive
         thrssdeecosc=10., \
                
         # threshold LS periodogram power for disposing the target as positive
         thrslspecosc=0.2, \
                
         # type of model for lensing
         ## 'phdy': photodynamically calculated
         ## 'gaus': Gaussian
         typemodllens='phdy', \

         ### type of priors for stars: 'tici', 'exar', 'inpt'
         typepriostar=None, \

         # type of priors for planets
         typepriocomp=None, \
         
         # Boolean flag to turn on transit for each companion
         booltrancomp=None, \

         ### photometric and RV model
         #### means
         rratcompprio=None, \
         rsmacompprio=None, \
         epocmtracompprio=None, \
         pericompprio=None, \
         cosicompprio=None, \
         ecoscompprio=None, \
         esincompprio=None, \
         rvelsemaprio=None, \
         #### uncertainties
         stdvrratcompprio=None, \
         stdvrsmacompprio=None, \
         stdvepocmtracompprio=None, \
         stdvpericompprio=None, \
         stdvcosicompprio=None, \
         stdvecoscompprio=None, \
         stdvesincompprio=None, \
         stdvrvelsemaprio=None, \
        
         ### others 
         #### mean
         projoblqprio=None, \
         #### uncertainties
         stdvprojoblqprio=None, \

         radistar=None, \
         massstar=None, \
         tmptstar=None, \
         rascstar=None, \
         declstar=None, \
         vsiistar=None, \
         
         vmagsyst=None, \
         jmagsyst=None, \
         hmagsyst=None, \
         kmagsyst=None, \

         stdvradistar=None, \
         stdvmassstar=None, \
         stdvtmptstar=None, \
         stdvrascstar=None, \
         stdvdeclstar=None, \
         stdvvsiistar=None, \

         ## Boolean flag to perform inference on the phase-folded (onto the period of the first planet) and binned data
         boolinfefoldbind=False, \
         ## Boolean flag to model the out-of-transit data to learn a background model
         boolallebkgdgaus=False, \
         # output
         ### list of offsets for the planet annotations in the TSM/ESM plot
         offstextatmoraditmpt=None, \
         offstextatmoradimetr=None, \
         
         # exoplanet specifics
         # planet names
         # string to pull the priors from the NASA Exoplanet Archive
         strgexar=None, \

         ## list of letters to be assigned to planets
         liststrgcomp=None, \
         
         # energy scale over which to detrend the inferred spectrum
         enerscalbdtr=None, \

         ## list of colors to be assigned to planets
         listcolrcomp=None, \
         
         ## Boolean flag to assign them letters *after* ordering them in orbital period, unless liststrgcomp is specified by the user
         boolordrplanname=True, \
        
         # population contexualization
         ## Boolean flag to include the ExoFOP catalog in the comparisons to exoplanet population
         boolexofpopl=True, \
        
         # Boolean flag to ignore any existing file and overwrite
         boolwritover=False, \
         
         # Boolean flag to diagnose the code using potentially computationally-expensive sanity checks, which may slow down the execution
         booldiag=False, \
         
         # type of verbosity
         typeverb=1, \

        ):
    '''
    Main function of the miletos pipeline.
    '''
    
    # construct global object
    gdat = tdpy.gdatstrt()
    
    # copy locals (inputs) to the global object
    dictinpt = dict(locals())
    for attr, valu in dictinpt.items():
        if '__' not in attr and attr != 'gdat':
            setattr(gdat, attr, valu)

    # paths
    gdat.pathbasemile = os.environ['MILETOS_DATA_PATH'] + '/'
    if gdat.pathbase is None:
        gdat.pathbase = gdat.pathbasemile
    
    # measure initial time
    gdat.timeinit = modutime.time()

    # string for date and time
    gdat.strgtimestmp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if gdat.typeverb > 0:
        print('miletos initialized at %s...' % gdat.strgtimestmp)
    
    # check input arguments
    if not gdat.boolplot and gdat.boolplottser:
        raise Exception('')
    
    if gdat.boolplotvisi and not gdat.boolcalcvisi:
        raise Exception('')
    
    if gdat.boolplotvisi is None:
        gdat.boolplotvisi = gdat.boolcalcvisi
    
    if gdat.typemodlener is None:
        gdat.typemodlener = 'iter'
    
    # paths
    gdat.pathbaselygo = os.environ['LYGOS_DATA_PATH'] + '/'
    
    # check input arguments
    if not (gdat.pathtarg is not None and gdat.pathbase is None and gdat.pathdatatarg is None and gdat.pathimagtarg is None or \
            gdat.pathtarg is None and gdat.pathbase is not None and gdat.pathdatatarg is None and gdat.pathimagtarg is None or \
            gdat.pathtarg is None and gdat.pathbase is None and gdat.pathdatatarg is not None and gdat.pathimagtarg is not None):
        print('gdat.pathtarg')
        print(gdat.pathtarg)
        print('gdat.pathbase')
        print(gdat.pathbase)
        print('gdat.pathdatatarg')
        print(gdat.pathdatatarg)
        print('gdat.pathimagtarg')
        print(gdat.pathimagtarg)
        raise Exception('')
    
    ## ensure that target and star coordinates are not provided separately
    if gdat.rasctarg is not None and gdat.rascstar is not None:
        raise Exception('')
    if gdat.decltarg is not None and gdat.declstar is not None:
        raise Exception('')

    ## ensure target identifiers are not conflicting
    if gdat.listarrytser is None:
        if gdat.ticitarg is None and gdat.strgmast is None and gdat.toiitarg is None and (gdat.rasctarg is None or gdat.decltarg is None):
            print('Warning: No TIC ID (ticitarg), RA&DEC (rasctarg and decltarg), MAST key (strgmast) or a TOI ID (toiitarg) wad provided.')
        
        if gdat.ticitarg is not None and (gdat.strgmast is not None or gdat.toiitarg is not None or gdat.rasctarg is not None or gdat.decltarg is not None):
            raise Exception('Either a TIC ID (ticitarg), RA&DEC (rasctarg and decltarg), MAST key (strgmast) or a TOI ID (toiitarg) should be provided.')
        if gdat.strgmast is not None and (gdat.ticitarg is not None or gdat.toiitarg is not None or gdat.rasctarg is not None or gdat.decltarg is not None):
            raise Exception('Either a TIC ID (ticitarg), RA&DEC (rasctarg and decltarg), MAST key (strgmast) or a TOI ID (toiitarg) should be provided.')
        if gdat.toiitarg is not None and (gdat.strgmast is not None or gdat.ticitarg is not None or gdat.rasctarg is not None or gdat.decltarg is not None):
            raise Exception('Either a TIC ID (ticitarg), RA&DEC (rasctarg and decltarg), MAST key (strgmast) or a TOI ID (toiitarg) should be provided.')
        if gdat.strgmast is not None and (gdat.ticitarg is not None or gdat.toiitarg is not None or gdat.rasctarg is not None or gdat.decltarg is not None):
            raise Exception('Either a TIC ID (ticitarg), RA&DEC (rasctarg and decltarg), MAST key (strgmast) or a TOI ID (toiitarg) should be provided.')
    
    # dictionary to be returned
    gdat.dictmileoutp = dict()
    
    # list of models to be fitted to the data
    gdat.boolmodlpsys = False
    gdat.boolmodltran = False
    gdat.boolsrchpbox = False
    gdat.boolcalclspe = False
    
    if gdat.listtypemodl is None:
        gdat.listtypemodl = []
    
    if gdat.typeverb > 0:
        print('List of model types: %s' % gdat.listtypemodl)
    
    # Boolean flag to perform inference
    gdat.boolinfe = len(gdat.listtypemodl) > 0
    if gdat.booltserdata:
        if gdat.boolplottser is None:
            gdat.boolplottser = gdat.boolplot
        
        if gdat.boolplotdvrp is None:
            gdat.boolplotdvrp = gdat.boolplot
        
        if gdat.dictlygoinpt is None:
            gdat.dictlygoinpt = dict()
        
        if gdat.dictlcurtessinpt is None:
            gdat.dictlcurtessinpt = dict()

        # data validation (DV) report
        ## list of dictionaries holding the paths and DV report positions of plots
        if gdat.boolplot:
            gdat.listdictdvrp = [[]]
        
        gdat.boolmodlcosc = 'cosc' in gdat.listtypemodl
        gdat.boolmodlpsys = 'psys' in gdat.listtypemodl or 'psyspcur' in gdat.listtypemodl or 'psysttvr' in gdat.listtypemodl
        gdat.boolmodlpcur = 'pcur' in gdat.listtypemodl or 'psyspcur' in gdat.listtypemodl
        gdat.boolmodltran = gdat.boolmodlpsys or gdat.boolmodlcosc
        
        if gdat.typeverb > 0:
            print('gdat.boolmodlcosc')
            print(gdat.boolmodlcosc)
            print('gdat.boolmodlpsys')
            print(gdat.boolmodlpsys)
            print('gdat.boolmodlpcur')
            print(gdat.boolmodlpcur)
            print('gdat.boolmodltran')
            print(gdat.boolmodltran)
    
    gdat.fitt = tdpy.gdatstrt()
    
    setp_para_defa(gdat, 'fitt', 'typemodlbase', 'cons')
    if 'supn' in gdat.listtypemodl:
        # 'linr': quadratic
        # 'quad': quadratic
        # 'cubc': cubic
        # 'gpro': GP process
        setp_para_defa(gdat, 'fitt', 'typemodlsupn', 'quad')
        
        # 'none': No excess
        # 'bump': single bump
        setp_para_defa(gdat, 'fitt', 'typemodlexcs', 'bump')

    if (gdat.boolcalcvisi or gdat.boolplotpopl or gdat.booltserdata) and (gdat.toiitarg is not None or gdat.ticitarg is not None) and not ('supn' in gdat.listtypemodl):
        gdat.dictexof = ephesus.retr_dicttoii()

    # conversion factors
    gdat.dictfact = tdpy.retr_factconv()

    # settings
    ## plotting
    gdat.numbcyclcolrplot = 300
    gdat.alphraww = 0.2
    
    if gdat.lablener is None:
        gdat.lablener = 'Wavelength'
    
    if gdat.enerscalbdtr is None:
        gdat.enerscalbdtr = 0.1 # [um]

    gdat.figrsize = [6, 4]
    gdat.figrsizeydob = [8., 4.]
    gdat.figrsizeydobskin = [8., 2.5]
        
    gdat.listfeatstar = ['radistar', 'massstar', 'tmptstar', 'rascstar', 'declstar', 'vsiistar', 'jmagsyst']
    gdat.listfeatstarpopl = ['radicomp', 'masscomp', 'tmptplan', 'radistar', 'jmagsyst', 'kmagsyst', 'tmptstar']
    
    if gdat.boolplotpopl:
        gdat.liststrgpopl = []
        if gdat.boolmodlpsys:
            gdat.liststrgpopl += ['exar']
            if gdat.toiitarg is not None:
                gdat.liststrgpopl += ['exof']
        gdat.numbpopl = len(gdat.liststrgpopl)
    
    # model
    # type of likelihood
    ## 'sing': assume model is a single realization
    ## 'gpro': assume model is a Gaussian Process (GP)
    if gdat.fitt.typemodlbase == 'gpro':
        gdat.typellik = 'gpro'
    else:
        gdat.typellik = 'sing'

    # determine target identifiers
    if gdat.ticitarg is not None:
        gdat.typetarg = 'tici'
        if gdat.typeverb > 0:
            print('A TIC ID was provided as target identifier.')
        
        # check if this TIC is a TOI
        if gdat.boolmodlpsys:
            indx = np.where(gdat.dictexof['tici'] == gdat.ticitarg)[0]
            if indx.size > 0:
                gdat.toiitarg = int(str(gdat.dictexof['toii'][indx[0]]).split('.')[0])
                if gdat.typeverb > 0:
                    print('Matched the input TIC ID with TOI-%d.' % gdat.toiitarg)
        
        gdat.strgmast = 'TIC %d' % gdat.ticitarg

    elif gdat.toiitarg is not None:
        gdat.typetarg = 'toii'
        if gdat.typeverb > 0:
            print('A TOI ID (%d) was provided as target identifier.' % gdat.toiitarg)
        # determine TIC ID
        gdat.strgtoiibase = str(gdat.toiitarg)
        indx = []
        for k, strg in enumerate(gdat.dictexof['toii']):
            if str(strg).split('.')[0] == gdat.strgtoiibase:
                indx.append(k)
        indx = np.array(indx)
        if indx.size == 0:
            print('Did not find the TOI in the ExoFOP-TESS TOI list.')
            print('gdat.dictexof[TOI]')
            summgene(gdat.dictexof['toii'])
            raise Exception('')
        gdat.ticitarg = gdat.dictexof['tici'][indx[0]]

        if gdat.strgexar is None:
            gdat.strgexar = 'TOI-%d' % gdat.toiitarg
        gdat.strgmast = 'TIC %d' % gdat.ticitarg

    elif gdat.strgmast is not None:
        gdat.typetarg = 'mast'
        if gdat.typeverb > 0:
            print('A MAST key (%s) was provided as target identifier.' % gdat.strgmast)

    elif gdat.rasctarg is not None and gdat.decltarg is not None:
        gdat.typetarg = 'posi'
        if gdat.typeverb > 0:
            print('RA and DEC (%g %g) are provided as target identifier.' % (gdat.rasctarg, gdat.decltarg))
        gdat.strgmast = '%g %g' % (gdat.rasctarg, gdat.decltarg)
    elif gdat.listarrytser is not None:
        gdat.typetarg = 'inpt'

        if gdat.labltarg is None:
            raise Exception('')
    else:
        # hypothetical target
        gdat.typetarg = 'hypo'

    # Boolean flag indicating whether MAST has been searched already
    boolsrchmast = False
    
    if (gdat.typetarg == 'tici' or gdat.typetarg == 'toii' or gdat.typetarg == 'mast') and not boolsrchmast:
        # temp -- check that the closest TIC to a given TIC is itself
        if gdat.typeverb > 0:
            print('Querying the TIC within %s as to get the RA, DEC, Tmag, and TIC ID of the closest source to the MAST keywrod %s...' % (strgradi, gdat.strgmast))
        listdictticinear = astroquery.mast.Catalogs.query_region(gdat.strgmast, radius=strgradi, catalog="TIC")
        boolsrchmast = True
        if gdat.typeverb > 0:
            print('Found %d TIC sources.' % len(listdictticinear))
        if listdictticinear[0]['dstArcSec'] < 0.2:
            gdat.ticitarg = int(listdictticinear[0]['ID'])
            gdat.rasctarg = listdictticinear[0]['ra']
            gdat.decltarg = listdictticinear[0]['dec']
            gdat.tmagtarg = listdictticinear[0]['Tmag']

    if gdat.typeverb > 0:
        print('gdat.typetarg')
        print(gdat.typetarg)

    if gdat.listtsec is not None and gdat.typetarg != 'inpt':
        raise Exception('List of TESS sectors can only be input when typetarg is "inpt".')
    
    # check if any GPU is available
    import GPUtil
    temp = GPUtil.getGPUs()
    print('temp')
    print(temp)

    gdat.maxmnumbiterbdtr = 5
    
    if gdat.typeverb > 0:
        print('gdat.ticitarg')
        print(gdat.ticitarg)
        print('gdat.strgmast')
        print(gdat.strgmast)
        print('gdat.rasctarg')
        print(gdat.rasctarg)
        print('gdat.decltarg')
        print(gdat.decltarg)
        print('gdat.toiitarg')
        print(gdat.toiitarg)
    
    # priors
    if gdat.typepriostar is None:
        if gdat.radistar is not None:
            gdat.typepriostar = 'inpt'
        else:
            gdat.typepriostar = 'tici'
    
    if gdat.typeverb > 0:
        if ('psys' in gdat.listtypemodl or 'psyspcur' in gdat.listtypemodl):
            print('Stellar parameter prior type: %s' % gdat.typepriostar)
    
    # number of Boolean signal outputs
    gdat.numbtypeposi = 4
    gdat.indxtypeposi = np.arange(gdat.numbtypeposi)
    
    if ('psys' in gdat.listtypemodl or 'psyspcur' in gdat.listtypemodl):
        print('gdat.typemodllmdkener')
        print(gdat.typemodllmdkener)

    if gdat.typeverb > 0:
        print('boolplotpopl')
        print(boolplotpopl)
        if gdat.booltserdata:
            print('gdat.boolplottser')
            print(gdat.boolplottser)
    
    ## NASA Exoplanet Archive
    if gdat.boolplotpopl:
        gdat.dictexar = ephesus.retr_dictexar(strgelem='comp', typeverb=gdat.typeverb)
    
    if gdat.strgclus is None:
        gdat.pathclus = gdat.pathbase
    else:
        #gdat.strgclus += '/'
        if gdat.typeverb > 0:
            print('gdat.strgclus')
            print(gdat.strgclus)
        # data path for the cluster of targets
        gdat.pathclus = gdat.pathbase + '%s/' % gdat.strgclus
        gdat.pathdataclus = gdat.pathclus + 'data/'
        gdat.pathimagclus = gdat.pathclus + 'imag/'
    
    if gdat.labltarg is None:
        if gdat.typetarg == 'mast':
            gdat.labltarg = gdat.strgmast
        if gdat.typetarg == 'toii':
            gdat.labltarg = 'TOI-%d' % gdat.toiitarg
        if gdat.typetarg == 'tici':
            gdat.labltarg = 'TIC %d' % gdat.ticitarg
        if gdat.typetarg == 'posi':
            gdat.labltarg = 'RA=%.4g, DEC=%.4g' % (gdat.rasctarg, gdat.decltarg)
        if gdat.typetarg == 'hypo':
            gdat.labltarg = 'Sim Target'
    
    if gdat.typeverb > 0:
        print('gdat.labltarg')
        print(gdat.labltarg)
    
    # the string that describes the target
    if gdat.strgtarg is None:
        gdat.strgtarg = ''.join(gdat.labltarg.split(' '))
    
    # the path for the target
    if gdat.pathtarg is None:
        
        gdat.pathtarg = gdat.pathclus + '%s/' % (gdat.strgtarg)
        
        if gdat.strgcnfg is None:
            strgcnfgtemp = ''
        else:
            strgcnfgtemp = gdat.strgcnfg + '/'
        
        gdat.pathtargruns = gdat.pathtarg + strgcnfgtemp
        
        gdat.pathdatatarg = gdat.pathtargruns + 'data/'
        gdat.pathimagtarg = gdat.pathtargruns + 'imag/'

    if gdat.strgcnfg is None:
        gdat.strgcnfg = ''
    else:
        gdat.strgcnfg = '_' + gdat.strgcnfg
    
    if gdat.typeverb > 0:
        print('gdat.strgtarg')
        print(gdat.strgtarg)
    
    # check if the run has been completed before
    path = gdat.pathdatatarg + 'dictmileoutp.pickle'
    if not gdat.boolwritover and os.path.exists(path):
        
        if gdat.typeverb > 0:
            print('Reading from %s...' % path)
        with open(path, 'rb') as objthand:
            gdat.dictmileoutp = pickle.load(objthand)
        
        return gdat.dictmileoutp

    if gdat.strgtarg == '' or gdat.strgtarg is None or gdat.strgtarg == 'None' or len(gdat.strgtarg) == 0:
        raise Exception('')
    
    for name in ['strgtarg', 'pathtarg']:
        gdat.dictmileoutp[name] = getattr(gdat, name)

    if gdat.booltserdata:
        
        if gdat.listlablinst is None:
            gdat.listlablinst = [['TESS'], []]
        
        gdat.liststrgdatatser = ['lcur', 'rvel']
        gdat.numbdatatser = len(gdat.liststrgdatatser)
        gdat.indxdatatser = np.arange(gdat.numbdatatser)

        if gdat.typeverb > 0:
            print('gdat.listlablinst')
            print(gdat.listlablinst)
        
        gdat.numbinst = np.empty(gdat.numbdatatser, dtype=int)
        gdat.indxinst = [[] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            gdat.numbinst[b] = len(gdat.listlablinst[b])
            gdat.indxinst[b] = np.arange(gdat.numbinst[b])
        
        if gdat.typeverb > 0:
            print('gdat.numbinst')
            print(gdat.numbinst)
        
        if gdat.liststrginst is None:
            gdat.liststrginst = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    gdat.liststrginst[b][p] = ''.join(gdat.listlablinst[b][p].split(' '))
        
        if gdat.booldiag:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    if len(gdat.liststrginst[b][p]) != len(gdat.listlablinst[b][p]):
                        raise Exception('')
        
        if gdat.typeverb > 0:
            print('gdat.strgcnfg')
            print(gdat.strgcnfg)
            print('gdat.liststrginst')
            print(gdat.liststrginst)

        gdat.pathalle = dict()
        gdat.objtalle = dict()
        
    if gdat.typetarg != 'inpt':
        if gdat.typetarg == 'mast':
            strgmast = gdat.strgmast
            rasctarg = None
            decltarg = None
            ticitarg = None
        if gdat.typetarg == 'toii':
            strgmast = None
            rasctarg = None
            decltarg = None
            ticitarg = gdat.ticitarg
        if gdat.typetarg == 'tici':
            strgmast = None
            rasctarg = None
            decltarg = None
            ticitarg = gdat.ticitarg
        if gdat.typetarg == 'posi':
            strgmast = None
            rasctarg = gdat.rasctarg
            decltarg = gdat.decltarg
            ticitarg = None
    
    if gdat.booltserdata:
        
        # list of data types ('obsd' or 'simutoyy') for each instrument for both light curve and RV data
        if gdat.liststrgtypedata is None:
            gdat.liststrgtypedata = [[] for b in gdat.indxdatatser]
            for b in gdat.indxdatatser:
                gdat.liststrgtypedata[b] = ['obsd' for p in gdat.indxinst[b]]
        
        if gdat.typeverb > 0:
            print('gdat.liststrgtypedata')
            print(gdat.liststrgtypedata)

        # get data
        gdat.boolretrtess = False
        gdat.boolsimurflx = False
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                if gdat.liststrgtypedata[b][p].startswith('simu'):
                    gdat.boolsimurflx = True
                if gdat.liststrginst[b][p] == 'TESS' and not gdat.liststrgtypedata[b][p].startswith('simugenelcur') and \
                                                                                    not gdat.liststrgtypedata[b][p].startswith('inpt'):
                    gdat.boolretrtess = True
        
        if gdat.typeverb > 0:
            print('gdat.boolsimurflx')
            print(gdat.boolsimurflx)
            print('gdat.boolretrtess')
            print(gdat.boolretrtess)
        
        if gdat.boolretrtess:
            gdat.dictlcurtessinpt['ticitarg'] = ticitarg
            gdat.dictlcurtessinpt['strgmast'] = strgmast
            gdat.dictlcurtessinpt['rasctarg'] = rasctarg
            
            if gdat.boolsimurflx:
                gdat.dictlcurtessinpt['strgtypedata'] = 'simugenelcur'
            else:
                gdat.dictlcurtessinpt['strgtypedata'] = 'obsd'
            gdat.dictlcurtessinpt['decltarg'] = decltarg
            gdat.dictlcurtessinpt['labltarg'] = gdat.labltarg
            gdat.dictlcurtessinpt['booldiag'] = gdat.booldiag
            gdat.dictlygoinpt['pathtarg'] = gdat.pathtargruns + 'lygos/'
            if not 'typepsfninfe' in gdat.dictlygoinpt:
                gdat.dictlygoinpt['typepsfninfe'] = 'fixd'
                #gdat.dictlygoinpt['maxmradisrchmast'] = maxmradisrchmast
            gdat.dictlcurtessinpt['dictlygoinpt'] = gdat.dictlygoinpt

            arrylcurtess, gdat.arrytsersapp, gdat.arrytserpdcc, listarrylcurtess, gdat.listarrytsersapp, gdat.listarrytserpdcc, \
                                  gdat.listtsec, gdat.listtcam, gdat.listtccd, listpathdownspoclcur, gdat.dictlygooutp = \
                                  retr_lcurtess( \
                                                        **gdat.dictlcurtessinpt, \
                                                       )
            
            gdat.dictmileoutp['listtsec'] = gdat.listtsec
            print('List of sectors for miletos:')
            print(gdat.listtsec)
            
            if gdat.dictlygooutp is not None:
                for name in gdat.dictlygooutp:
                    gdat.dictmileoutp['lygo_' + name] = gdat.dictlygooutp[name]
            
            # check if there is any data
            if len(listarrylcurtess) == 0:
                if gdat.typeverb > 0:
                    print('No TESS data found. Returning...')
            
        if gdat.boolmodlpsys:
            if gdat.strgexar is None:
                gdat.strgexar = gdat.strgmast
    
            if gdat.typeverb > 0:
                print('gdat.strgexar')
                print(gdat.strgexar)

            # grab object features from NASA Excoplanet Archive
            gdat.dictexartarg = ephesus.retr_dictexar(strgexar=gdat.strgexar, strgelem='comp', typeverb=gdat.typeverb)
            
            if gdat.typeverb > 0:
                if gdat.dictexartarg is None:
                    print('The target name was **not** found in the NASA Exoplanet Archive planetary systems composite table.')
                else:
                    print('The target name was found in the NASA Exoplanet Archive planetary systems composite table.')
            
            # grab object features from ExoFOP
            if gdat.toiitarg is not None:
                gdat.dictexoftarg = ephesus.retr_dicttoii(toiitarg=gdat.toiitarg)
            else:
                gdat.dictexoftarg = None
            gdat.boolexof = gdat.toiitarg is not None and gdat.dictexoftarg is not None
            gdat.boolexar = gdat.strgexar is not None and gdat.dictexartarg is not None or gdat.typepriocomp == 'exar'
            
            if gdat.typepriocomp is None:
                if gdat.epocmtracompprio is not None:
                    gdat.typepriocomp = 'inpt'
                elif gdat.boolexar:
                    gdat.typepriocomp = 'exar'
                elif gdat.boolexof:
                    gdat.typepriocomp = 'exof'
                else:
                    gdat.typepriocomp = 'pdim'

            if gdat.typeverb > 0:
                print('Companion prior type: %s' % gdat.typepriocomp)
            
            if not gdat.boolexar and gdat.typepriocomp == 'exar':
                raise Exception('')
    
        ## list of analysis types
        ### 'pdim': search for periodic dimmings
        ### 'pinc': search for periodic increases
        ### 'lspe': search for sinusoid variability
        ### 'mfil': matched filter
        if gdat.listtypeanls is None:
            gdat.listtypeanls = ['lspe']
        if ('psys' in gdat.listtypemodl or 'psyspcur' in gdat.listtypemodl) and gdat.typepriocomp == 'pdim':
            gdat.listtypeanls += ['pdim']
        if 'cosc' in gdat.listtypemodl:
            gdat.listtypeanls += ['pinc']

        if gdat.typeverb > 0:
            print('List of analysis types: %s' % gdat.listtypeanls)
        
        if gdat.boolbdtr is None:
            if ('psys' in gdat.listtypemodl or 'psyspcur' in gdat.listtypemodl):
                gdat.boolbdtr = True
            else:
                gdat.boolbdtr = False
        
        if gdat.typeverb > 0:
            if gdat.boolbdtr:
                print('Will detrend the photometric time-series before estimating the priors...')
            else:
                print('Will NOT detrend the photometric time-series before estimating the priors...')
        
        ## Boolean flag to calculate the power spectral density
        gdat.boolcalclspe = 'lspe' in gdat.listtypeanls

        # Boolean flag to execute a search for periodic boxes
        gdat.boolsrchpdim = 'pdim' in gdat.listtypeanls

        # Boolean flag to execute a search for periodic boxes
        gdat.boolsrchpinc = 'pinc' in gdat.listtypeanls
        
        gdat.boolsrchpbox = gdat.boolsrchpinc or gdat.boolsrchpdim

        # Boolean flag to execute a search for flares
        if 'flar' in gdat.listtypemodl:
            gdat.boolsrchflar = True
        else:
            gdat.boolsrchflar = False
        if gdat.typeverb > 0:
            print('gdat.boolcalclspe') 
            print(gdat.boolcalclspe)
            print('gdat.boolsrchpdim') 
            print(gdat.boolsrchpdim)
            print('gdat.boolsrchpinc') 
            print(gdat.boolsrchpinc)
            print('gdat.boolsrchpbox') 
            print(gdat.boolsrchpbox)
            print('gdat.boolsrchflar') 
            print(gdat.boolsrchflar)
        
        gdat.liststrgpdfn = ['prio']
        if gdat.boolmodlpsys:
            gdat.liststrgpdfn += ['post']

        if gdat.typeverb > 0:
            print('gdat.liststrgpdfn')
            print(gdat.liststrgpdfn)
        
        print('gdat.boolmodlpsys')
        print(gdat.boolmodlpsys)
        print('gdat.boolplotpopl')
        print(gdat.boolplotpopl)
        
        if gdat.boolmodlpsys and gdat.boolplotpopl:
            

            gdat.pathimagfeat = gdat.pathimagtarg + 'feat/'
            for strgpdfn in gdat.liststrgpdfn:
                pathimagpdfn = gdat.pathimagfeat + strgpdfn + '/'
                setattr(gdat, 'pathimagfeatplan' + strgpdfn, pathimagpdfn + 'featplan/')
                setattr(gdat, 'pathimagfeatsyst' + strgpdfn, pathimagpdfn + 'featsyst/')
                setattr(gdat, 'pathimagdataplan' + strgpdfn, pathimagpdfn + 'dataplan/')
    
    # make folders
    for attr, valu in gdat.__dict__.items():
        if attr.startswith('path') and valu is not None and not isinstance(valu, dict) and valu.endswith('/'):
            os.system('mkdir -p %s' % valu)
            
    gdat.numbcomp = None
    gdat.epocmtracompprio = None
    gdat.pericompprio = None
    gdat.duraprio = None
    
    if gdat.booltserdata:
        
        if gdat.boolmodlpsys:
        
            if gdat.typepriocomp == 'exar':
                gdat.pericompprio = gdat.dictexartarg['pericomp']
                gdat.rsmacompprio = gdat.dictexartarg['rsmacomp']
                gdat.rratcompprio = gdat.dictexartarg['rratcomp']
                gdat.deptprio = gdat.dictexartarg['depttrancomp']
                gdat.cosicompprio = gdat.dictexartarg['cosicomp']
                gdat.epocmtracompprio = gdat.dictexartarg['epocmtracomp']

                gdat.duraprio = gdat.dictexartarg['duratrantotl']
                indx = np.where(~np.isfinite(gdat.duraprio) & gdat.dictexartarg['booltran'])[0]
                if indx.size > 0:
                    dcyc = 0.15
                    if gdat.typeverb > 0:
                        print('Duration from the Exoplanet Archive Composite PS table is infite for companions. Assuming a duty cycle of %.3g.' % dcyc)
                    gdat.duraprio[indx] = gdat.pericompprio[indx] * dcyc
            if gdat.typepriocomp == 'exof':
                if gdat.typeverb > 0:
                    print('A TOI ID is provided. Retreiving the TCE attributes from ExoFOP-TESS...')
                
                if gdat.epocmtracompprio is None:
                    gdat.epocmtracompprio = gdat.dictexoftarg['epocmtracomp']
                if gdat.pericompprio is None:
                    gdat.pericompprio = gdat.dictexoftarg['pericomp']
                gdat.deptprio = gdat.dictexoftarg['depttrancomp']
                gdat.duraprio = gdat.dictexoftarg['duratrantotl']
                if gdat.cosicompprio is None:
                    gdat.cosicompprio = np.zeros_like(gdat.epocmtracompprio)

            if gdat.typepriocomp == 'inpt':
                if gdat.rratcompprio is None:
                    gdat.rratcompprio = 0.1 + np.zeros_like(gdat.epocmtracompprio)
                if gdat.rsmacompprio is None:
                    gdat.rsmacompprio = 0.2 * gdat.pericompprio**(-2. / 3.)
                
                if gdat.typeverb > 0:
                    print('gdat.cosicompprio')
                    print(gdat.cosicompprio)

                if gdat.cosicompprio is None:
                    gdat.cosicompprio = np.zeros_like(gdat.epocmtracompprio)
                gdat.duraprio = ephesus.retr_dura(gdat.pericompprio, gdat.rsmacompprio, gdat.cosicompprio)
                gdat.deptprio = 1e3 * gdat.rratcompprio**2
            
            # check MAST
            if gdat.typetarg != 'inpt' and gdat.strgmast is None:
                gdat.strgmast = gdat.labltarg

            if gdat.typeverb > 0:
                print('gdat.strgmast')
                print(gdat.strgmast)
            
            if not gdat.boolforcoffl and gdat.strgmast is not None and not boolsrchmast:
                listdictticinear = astroquery.mast.Catalogs.query_object(gdat.strgmast, catalog='TIC', radius=strgradi)
                boolsrchmast = True
                if listdictticinear[0]['dstArcSec'] > 0.1:
                    if gdat.typeverb > 0:
                        print('The nearest source is more than 0.1 arcsec away from the target!')
                
                if gdat.typeverb > 0:
                    print('Found the target on MAST!')
                
                gdat.rascstar = listdictticinear[0]['ra']
                gdat.declstar = listdictticinear[0]['dec']
                gdat.stdvrascstar = 0.
                gdat.stdvdeclstar = 0.
                if gdat.radistar is None:
                    
                    if gdat.typeverb > 0:
                        print('Setting the stellar radius from the TIC.')
                    
                    gdat.radistar = listdictticinear[0]['rad']
                    gdat.stdvradistar = listdictticinear[0]['e_rad']
                    
                    if gdat.typeverb > 0:
                        if not np.isfinite(gdat.radistar):
                            print('Warning! TIC stellar radius is not finite.')
                        if not np.isfinite(gdat.radistar):
                            print('Warning! TIC stellar radius uncertainty is not finite.')
                if gdat.massstar is None:
                    
                    if gdat.typeverb > 0:
                        print('Setting the stellar mass from the TIC.')
                    
                    gdat.massstar = listdictticinear[0]['mass']
                    gdat.stdvmassstar = listdictticinear[0]['e_mass']
                    
                    if gdat.typeverb > 0:
                        if not np.isfinite(gdat.massstar):
                            print('Warning! TIC stellar mass is not finite.')
                        if not np.isfinite(gdat.stdvmassstar):
                            print('Warning! TIC stellar mass uncertainty is not finite.')
                if gdat.tmptstar is None:
                    
                    if gdat.typeverb > 0:
                        print('Setting the stellar temperature from the TIC.')
                    
                    gdat.tmptstar = listdictticinear[0]['Teff']
                    gdat.stdvtmptstar = listdictticinear[0]['e_Teff']
                    
                    if gdat.typeverb > 0:
                        if not np.isfinite(gdat.tmptstar):
                            print('Warning! TIC stellar temperature is not finite.')
                        if not np.isfinite(gdat.tmptstar):
                            print('Warning! TIC stellar temperature uncertainty is not finite.')
                gdat.jmagsyst = listdictticinear[0]['Jmag']
                gdat.hmagsyst = listdictticinear[0]['Hmag']
                gdat.kmagsyst = listdictticinear[0]['Kmag']
                gdat.vmagsyst = listdictticinear[0]['Vmag']
        
        if gdat.boolsimurflx:
            
            if gdat.listener is not None:
                gdat.numbener = gdat.listener.size
            else:
                gdat.numbener = 1
            gdat.indxener = np.arange(gdat.numbener)
            
            gdat.true = tdpy.gdatstrt()
            
            setp_para_defa(gdat, 'true', 'typemodl', 'psys')

            setp_para_defa(gdat, 'true', 'typemodlsupn', 'quad')
            setp_para_defa(gdat, 'true', 'typemodlexcs', 'bump')

            print('gdat.pericompprio')
            print(gdat.pericompprio)
            print('gdat.rsmacompprio')
            print(gdat.rsmacompprio)
            print('gdat.cosicompprio')
            print(gdat.cosicompprio)
            print('gdat.rratcompprio')
            print(gdat.rratcompprio)
            
            # type of baseline
            ## 'cons': constant
            ## 'step': step function
            gdat.true.typemodlbase = 'cons'

            if gdat.true.typemodlbase == 'cons':
                setp_para_defa(gdat, 'true', 'cons', np.array([0.]))
            elif gdat.true.typemodlbase == 'step':
                setp_para_defa(gdat, 'true', 'consfrst', np.array([0.]))
                setp_para_defa(gdat, 'true', 'consseco', np.array([0.]))
                setp_para_defa(gdat, 'true', 'timestep', np.array([0.]))
                setp_para_defa(gdat, 'true', 'scalstep', np.array([1.]))
            
            if gdat.true.typemodl == 'psys' or gdat.true.typemodl == 'cosc':
                setp_para_defa(gdat, 'true', 'numbcomp', 1)

                gdat.true.indxcomp = np.arange(gdat.true.numbcomp)
            
                for namepara in ['epocmtra', 'peri', 'rsma', 'rrat']:
                    for j in gdat.true.indxcomp:
                        setp_para_defa(gdat, 'true', namepara + 'com%d' % j, getattr(gdat, namepara + 'compprio')[j])

                if gdat.true.typemodl == 'psys':
                    for j in gdat.true.indxcomp:
                        setp_para_defa(gdat, 'true', 'rratcom%d' % j, getattr(gdat, 'rratcompprio'))
                
                setp_para_defa(gdat, 'true', 'coeflmdklinr', 0.4)
                setp_para_defa(gdat, 'true', 'coeflmdkquad', 0.25)
                
                if gdat.true.typemodl == 'cosc':
                    setp_para_defa(gdat, 'true', 'radistar', 1.)
                    setp_para_defa(gdat, 'true', 'massstar', 1.)
                    setp_para_defa(gdat, 'true', 'masscom0', 1.)
            
            if gdat.true.typemodl == 'supn':
                # temp
                minmtimesupn = np.amin(gdat.true.listtime[0][0][0]) + 0. * (np.amax(gdat.true.listtime[0][0][0]) - np.amin(gdat.true.listtime[0][0][0]))
                maxmtimesupn = np.amin(gdat.true.listtime[0][0][0]) + 1. * (np.amax(gdat.true.listtime[0][0][0]) - np.amin(gdat.true.listtime[0][0][0]))
                timesupn = tdpy.icdf_self(0.25, minmtimesupn, maxmtimesupn) - gdat.timeoffs
                setp_para_defa(gdat, 'true', 'timesupn', timesupn)

                setp_para_defa(gdat, 'true', 'coeflinesupn', 0.)

                setp_para_defa(gdat, 'true', 'sigmgprobase', 2.) # [ppt]
                
                setp_para_defa(gdat, 'true', 'rhoogprobase', 0.1) # [day]
                                
                setp_para_defa(gdat, 'true', 'timebumpoffs', 0.5) # [day]
                                
                setp_para_defa(gdat, 'true', 'amplbump', 10.) # [ppt]
                                
                setp_para_defa(gdat, 'true', 'scalbump', 1.) # [day]
                                
                setp_para_defa(gdat, 'true', 'coefquadsupn', 0.5) # [ppt]
                                
        else:
            gdat.numbener = 1

        # determine number of chunks
        gdat.numbchun = [np.zeros(gdat.numbinst[b], dtype=int) - 1 for b in gdat.indxdatatser]
        
        if gdat.boolsimurflx:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    gdat.numbchun[b][p] = 1
        
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                
                if gdat.typetarg == 'path':
                    gdat.numbchun[b][p] = len(gdat.listpathdatainpt[b][p])
                elif gdat.liststrgtypedata[b][p] == 'inpt':
                    gdat.numbchun[b][p] = len(gdat.listarrytser['raww'][b][p])
                elif gdat.boolsimurflx:
                    gdat.numbchun[b][p] = 1
                elif b == 0 and gdat.liststrginst[b][p] == 'TESS':
                    gdat.numbchun[b][p] = len(listarrylcurtess)
                
                if gdat.numbchun[b][p] < -1:
                    print('')
                    print('gdat.numbchun was not properly defined.')
                    raise Exception('')
                
        gdat.indxchun = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                gdat.indxchun[b][p] = np.arange(gdat.numbchun[b][p], dtype=int)
                
        gdat.arrytser = dict()
        if gdat.listarrytser is None:
            gdat.listarrytser = dict()
            gdat.listarrytser['raww'] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        
        gdat.arrytser['raww'] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.arrytser['maskcust'] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.arrytser['bdtr'] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.arrytser['bdtrbind'] = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        
        gdat.listarrytser['maskcust'] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.listarrytser['temp'] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.listarrytser['trnd'] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.listarrytser['bdtr'] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.listarrytser['bdtrbind'] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        
        # load input data
        if gdat.listpathdatainpt is not None:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        arry = np.loadtxt(gdat.listpathdatainpt[b][p][y], delimiter=',', skiprows=1)
                        gdat.listarrytser['raww'][b][p][y] = np.empty((arry.shape[0], arry.shape[1], 3))
                        gdat.listarrytser['raww'][b][p][y][:, :, 0:2] = arry[:, :, 0:2]
                        gdat.listarrytser['raww'][b][p][y][:, :, 2] = 1e-4 * arry[:, :, 1]
                        indx = np.argsort(gdat.listarrytser['raww'][b][p][y][:, 0])
                        gdat.listarrytser['raww'][b][p][y] = gdat.listarrytser['raww'][b][p][y][indx, :, :]
                        indx = np.where(gdat.listarrytser['raww'][b][p][y][:, 1] < 1e6)[0]
                        gdat.listarrytser['raww'][b][p][y] = gdat.listarrytser['raww'][b][p][y][indx, :, :]
                        gdat.listisec = None
        
        if gdat.listarrytser['raww'][0] is None:
            
            gdat.listarrytser['raww'][0] = [[[] for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]]

            # load TESS data
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    if gdat.typetarg != 'inpt' and b == 0 and gdat.liststrginst[b][p] == 'TESS' and gdat.boolretrtess:
                        #gdat.arrytser['raww'][b][p] = arrylcurtess[:, None, :]
                        for y in gdat.indxchun[b][p]:
                            gdat.listarrytser['raww'][b][p][y] = listarrylcurtess[y][:, None, :]
        
        if gdat.boolsimurflx:

            gdat.true.listtime = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            gdat.true.time = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        if gdat.liststrginst[b][p] == 'TESS':
                            cade = 10. # [min]
                            delttime = cade / 60. / 24.
                            gdat.true.listtime[b][p][y] = 2459000. + np.concatenate([np.arange(0., 13.2, delttime), np.arange(14.2, 27.3, delttime)])
                        elif gdat.liststrginst[b][p] == 'JWST':
                            gdat.true.listtime[b][p][y] = 2459000. + np.arange(0.3, 0.7, 2. / 60. / 24.)
                        elif gdat.liststrginst[b][p] == 'LSST':
                            gdat.true.listtime[b][p][y] = 2459000. + np.random.rand(1000) * 10. * 365.
                        else:
                            raise Exception('')
                    gdat.true.time[b][p] = np.concatenate(gdat.true.listtime[b][p])
            
            gdat.time = gdat.true.time
            gdat.timeconc = [[] for b in gdat.indxdatatser]
            for b in gdat.indxdatatser:
                if len(gdat.time[b]) > 0:
                    gdat.timeconc[b] = np.concatenate(gdat.time[b])
            
        if gdat.boolsimurflx:
            # temporarily change gdat.typemodlener to 'full'
            ## save the value of gdat.typemodlener
            gdat.typemodlenertemp = gdat.typemodlener
            gdat.typemodlener = 'full'
            
            if gdat.numbener == 1 or gdat.typemodlener == 'full':
                gdat.numbenermodl = gdat.numbener
                gdat.numbeneriter = 1
            else:
                gdat.numbenermodl = 1
                gdat.numbeneriter = gdat.numbener

            gdat.indxenerthismodl = np.arange(gdat.numbener)
        
        if gdat.boolsimurflx:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        gdat.listarrytser['raww'][b][p][y] = np.empty((gdat.true.listtime[b][p][y].size, gdat.numbener, 3))
                        gdat.listarrytser['raww'][b][p][y][:, :, 0] = gdat.true.listtime[b][p][y][:, None]
            
        if gdat.timeoffs is None:
            timeoffs = 0.
            cntr = 0
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        print('gdat.listarrytser[raww][b][p][y]')
                        summgene(gdat.listarrytser['raww'][b][p][y])
                        timeoffs += np.sum(gdat.listarrytser['raww'][b][p][y][:, 0, 0])
                        cntr += gdat.listarrytser['raww'][b][p][y].shape[0]
            timeoffs /= cntr
            gdat.timeoffs = int(timeoffs / 1000.) * 1000.
        
        if gdat.boolsimurflx:
            
            dictparainpt = gdat.dicttrue
            gdat.true.dictrflxmodl = retr_rflxmodl_mile(gdat, gdat.true.time, dictparainpt, 'true')[0]
            gdat.true.dictrvelmodl = retr_rvelmodl_mile(gdat, gdat.true.time, dictparainpt, 'true')[0]
            
            if gdat.true.typemodlbase == 'gpro':
                dictrflx = retr_rflxmodl_mile_gpro(gdat, 'true', gdat.true.time, dictparainpt)
                gdat.true.dictrflxmodl['base'] = dictrflx['base']

            ## restore the value of gdat.typemodlener
            gdat.typemodlener = gdat.typemodlenertemp
            
            # generate flux data
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        
                        # noise per cadence
                        gdat.listarrytser['raww'][b][p][y][:, :, 2] = 1e-2
                        gdat.listarrytser['raww'][b][p][y][:, :, 1] = gdat.true.dictrflxmodl['totl']
                        
                        gdat.listarrytser['raww'][b][p][y][:, :, 1] += \
                                    np.random.randn(gdat.true.listtime[b][p][y].size * gdat.numbener).reshape((gdat.true.listtime[b][p][y].size, gdat.numbener)) * \
                                                                                                                            gdat.listarrytser['raww'][b][p][y][:, :, 2]
        
        if len(gdat.indxinst[0]) > 0:
            # define number of energy bins if any photometric data exist
            gdat.numbener = gdat.listarrytser['raww'][0][0][0].shape[1]
        
        # make white light curve
        if gdat.numbener > 1:
            
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        arrywhit = np.empty((gdat.listarrytser['raww'][b][p][y].shape[0], 3))
                        arrywhit[:, 0] = gdat.listarrytser['raww'][b][p][y][:, 0, 0]
                        arrywhit[:, 1] = np.mean(gdat.listarrytser['raww'][b][p][y][:, :, 1], 1)
                        arrywhit[:, 2] = np.sqrt(np.sum(gdat.listarrytser['raww'][b][p][y][:, :, 2]**2, 1)) / gdat.numbener
                        
                        arrytemp = np.empty((gdat.listarrytser['raww'][b][p][y].shape[0], gdat.numbener + 1, 3))
                        arrytemp[:, 0, :] = arrywhit
                        arrytemp[:, 1:, :] = gdat.listarrytser['raww'][b][p][y]
                        gdat.listarrytser['raww'][b][p][y] = arrytemp
        
        if gdat.typeverb > 0:
            print('gdat.numbener')
            print(gdat.numbener)
            
        if gdat.numbener == 1:
            gdat.numbenermodl = 1
            gdat.numbeneriter = 1
        elif gdat.typemodlener == 'full':
            gdat.numbenermodl = gdat.numbener
            gdat.numbeneriter = 2
        else:
            gdat.numbenermodl = 1
            gdat.numbeneriter = gdat.numbener + 1
        gdat.indxdataiter = np.arange(gdat.numbeneriter)
        gdat.indxenermodl = np.arange(gdat.numbenermodl)

        gdat.indxener = np.arange(gdat.numbener)
            
        if gdat.numbener > 1 and gdat.typeverb > 0:
            print('gdat.typemodlener')
            print(gdat.typemodlener)

        # list of strings to be attached to file names for each energy bin
        gdat.liststrgener = [[] for e in gdat.indxener]
        for e in gdat.indxener:
            gdat.liststrgener[e] = 'en%02d' % e

        # list of strings to be attached to file names for each energy bin
        gdat.liststrgeneriter = [[] for e in gdat.indxdataiter]
        for e in gdat.indxdataiter:
            if e == 0:
                if gdat.numbener > 1:
                    gdat.liststrgeneriter[0] = 'whit'
                else:
                    gdat.liststrgeneriter[0] = ''
            else:
                gdat.liststrgeneriter[e] = 'en%02d' % (e - 1)
        
        if gdat.typeverb > 0:
            print('gdat.liststrgeneriter')
            print(gdat.liststrgeneriter)

        # concatenate data across sectors
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                #if gdat.liststrgtypedata[b][p] == 'inpt' and gdat.liststrgtypedata[b][p].startswith('simu'):
                gdat.arrytser['raww'][b][p] = np.concatenate(gdat.listarrytser['raww'][b][p])
        
        if gdat.booldiag:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        if len(gdat.listarrytser['raww'][b][p][y]) == 0:
                            print('bpy')
                            print('%d, %d, %d' % (b, p, y))
                            print('gdat.listarrytser[raww][b][p][y]')
                            summgene(gdat.listarrytser['raww'][b][p][y])
                            raise Exception('')

        if gdat.liststrgchun is None:
            gdat.liststrgchun = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        if gdat.liststrginst[b][p] == 'TESS' and gdat.listtsec is not None:
                            gdat.liststrgchun[b][p][y] = 'sc%02d' % gdat.listtsec[y]
                        else:
                            gdat.liststrgchun[b][p][y] = 'ch%02d' % y
        
        # check the user-defined gdat.listpathdatainpt
        if gdat.listpathdatainpt is not None:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    if not isinstance(gdat.listpathdatainpt[b][p], list):
                        raise Exception('')
        
        if gdat.boolnormphot:
            gdat.labltserphot = 'Relative flux'
        else:
            gdat.labltserphot = 'ADC Counts [e$^-$/s]'
        gdat.listlabltser = [gdat.labltserphot, 'Radial Velocity [km/s]']
        gdat.liststrgtser = ['rflx', 'rvel']
        gdat.liststrgtseralle = ['flux', 'rv']
        
        if gdat.typeverb > 0:
            print('Light curve data: %s' % gdat.listlablinst[0])
            print('RV data: %s' % gdat.listlablinst[1])
        
        if gdat.offstextatmoraditmpt is None:
            gdat.offstextatmoraditmpt = [[0.3, -0.5], [0.3, -0.5], [0.3, -0.5], [0.3, 0.5]]
        if gdat.offstextatmoradimetr is None:
            gdat.offstextatmoradimetr = [[0.3, -0.5], [0.3, -0.5], [0.3, -0.5], [0.3, 0.5]]
    
    if gdat.typetarg == 'inpt':
        if gdat.vmagsyst is None:
            gdat.vmagsyst = 0.
        if gdat.jmagsyst is None:
            gdat.jmagsyst = 0.
        if gdat.hmagsyst is None:
            gdat.hmagsyst = 0.
        if gdat.kmagsyst is None:
            gdat.kmagsyst = 0.

    if gdat.booltserdata:
        # check availability of data 
        booldataaval = False
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                for y in gdat.indxchun[b][p]:
                    if len(gdat.listarrytser['raww'][b][p][y]) == 0:
                        print('bpy')
                        print(b, p, y)
                        print('gdat.indxchun')
                        print(gdat.indxchun)
                        raise Exception('')
                    if len(gdat.listarrytser['raww'][b][p][y]) > 0:
                        booldataaval = True
        if not booldataaval:
            if gdat.typeverb > 0:
                print('No data found. Returning...')
            return gdat.dictmileoutp
    
        # plot raw data
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                for y in gdat.indxchun[b][p]:
                    if gdat.boolplottser:
                        plot_tser(gdat, b, p, y, 'raww')
                if gdat.boolplottser:
                    gdat.arrytser['raww'][b][p] = np.concatenate(gdat.listarrytser['raww'][b][p], axis=0)
        
        if gdat.booldiag:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        if len(gdat.listarrytser['raww'][b][p][y]) == 0:
                            print('bpy')
                            print(b, p, y)
                            raise Exception('')
            
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    if not np.isfinite(gdat.arrytser['raww'][b][p]).all():
                        print('b, p')
                        print(b, p)
                        indxbadd = np.where(~np.isfinite(gdat.arrytser['raww'][b][p]))[0]
                        print('gdat.arrytser[raww][b][p]')
                        summgene(gdat.arrytser['raww'][b][p])
                        print('indxbadd')
                        summgene(indxbadd)
                        raise Exception('')
        
        # obtain 'maskcust' (obtained after custom mask, if any) time-series bundle after applying user-defined custom mask, if any
        if gdat.listlimttimemask is not None:
            
            if gdat.typeverb > 0:
                print('Masking the data...')
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    numbmask = len(gdat.listlimttimemask[b][p])
                    for y in gdat.indxchun[b][p]:
                        listindxtimemask = []
                        for k in range(numbmask):
                            indxtimemask = np.where((gdat.listarrytser['raww'][b][p][y][:, 0] < gdat.listlimttimemask[b][p][k][1]) & \
                                                    (gdat.listarrytser['raww'][b][p][y][:, 0] > gdat.listlimttimemask[b][p][k][0]))[0]
                            listindxtimemask.append(indxtimemask)
                        listindxtimemask = np.concatenate(listindxtimemask)
                        listindxtimegood = np.setdiff1d(np.arange(gdat.listarrytser['raww'][b][p][y].shape[0]), listindxtimemask)
                        gdat.listarrytser['maskcust'][b][p][y] = gdat.listarrytser['raww'][b][p][y][listindxtimegood, :]
                        if gdat.boolplottser:
                            plot_tser(gdat, b, p, y, 'maskcust')
                    gdat.arrytser['maskcust'][b][p] = np.concatenate(gdat.listarrytser['maskcust'][b][p], 0)
                    if gdat.boolplottser:
                        plot_tser(gdat, b, p, y, 'maskcust')
        else:
            gdat.arrytser['maskcust'] = gdat.arrytser['raww']
            gdat.listarrytser['maskcust'] = gdat.listarrytser['raww']
        
        # detrending
        ## determine whether to use any mask for detrending
        if gdat.boolmodltran and gdat.duraprio is not None and len(gdat.duraprio) > 0:
            # assign the prior orbital solution to the baseline-detrend mask
            gdat.epocmask = gdat.epocmtracompprio
            gdat.perimask = gdat.pericompprio
            gdat.duramask = 2. * gdat.duraprio
        else:
            gdat.epocmask = None
            gdat.perimask = None
            gdat.duramask = None
                            
        # obtain bdtrnotr time-series bundle, the baseline-detrended light curve with no masking due to identified transiting object
        if gdat.numbinst[0] > 0 and gdat.boolbdtr:
            gdat.listobjtspln = [[[[] for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]] for b in gdat.indxdatatser]
            gdat.indxsplnregi = [[[[] for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]] for b in gdat.indxdatatser]
            gdat.listindxtimeregi = [[[[] for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]] for b in gdat.indxdatatser]
            gdat.indxtimeregioutt = [[[[] for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]] for b in gdat.indxdatatser]
            
            gdat.numbiterbdtr = [[0 for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]]
            numbtimecutt = [[1 for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]]
            
            print('Listing all strings of detrending variables...')
            for z, timescalbdtrspln in enumerate(gdat.listtimescalbdtrspln):
                for r in range(gdat.maxmnumbiterbdtr):
                    strgarrybdtrinpt, strgarryclipoutp, strgarrybdtroutp, strgarryclipinpt, strgarrybdtrblin = retr_namebdtrclip(z, r)
                    gdat.listarrytser[strgarrybdtrinpt] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
                    gdat.listarrytser[strgarryclipoutp] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
                    gdat.listarrytser[strgarrybdtroutp] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
                    gdat.listarrytser[strgarryclipinpt] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
                    gdat.listarrytser[strgarrybdtrblin] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            
            # iterate over all detrending time scales (including, but not limited to the (first) time scale used for later analysis and model)
            gdat.indxenerclip = 0
            for z, timescalbdtrspln in enumerate(gdat.listtimescalbdtrspln):
                
                if timescalbdtrspln == 0:
                    continue
                
                strgarrybdtr = 'bdtrts%02d' % z
                gdat.listarrytser[strgarrybdtr] = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
                
                # baseline-detrending
                b = 0
                for p in gdat.indxinst[0]:
                    for y in gdat.indxchun[0][p]:
                        
                        gdat.listtimebrek = None

                        if gdat.typeverb > 0:
                            print('Detrending data from chunck %s...' % gdat.liststrgchun[0][p][y])
                        
                        indxtimetotl = np.arange(gdat.listarrytser['maskcust'][0][p][y].shape[0])
                        indxtimekeep = np.copy(indxtimetotl)
                        
                        r = 0
                        while True:
                            
                            if gdat.typeverb > 0:
                                print('Iteration %d' % r)
                            
                            # construct the variable names for this time scale and trial
                            strgarrybdtrinpt, strgarryclipoutp, strgarrybdtroutp, strgarryclipinpt, strgarrybdtrblin = retr_namebdtrclip(z, r)
                            
                            # perform trial mask
                            if gdat.typeverb > 0:
                                print('Trial filtering with %.3g percent of the data points...' % (100. * indxtimekeep.size / gdat.listarrytser['maskcust'][0][p][y].shape[0]))
                            gdat.listarrytser[strgarrybdtrinpt][0][p][y] = gdat.listarrytser['maskcust'][0][p][y][indxtimekeep, :, :]
                            
                            if gdat.booldiag and indxtimekeep.size < 2:
                                raise Exception('')

                            if gdat.boolplottser:
                                plot_tser(gdat, 0, p, y, strgarrybdtrinpt, booltoge=False)
                            
                            # perform trial detrending
                            if gdat.typeverb > 0:
                                print('Trial detrending into %s...' % strgarryclipinpt)
                            bdtr_wrap(gdat, 0, p, y, gdat.epocmask, gdat.perimask, gdat.duramask, strgarrybdtrinpt, strgarryclipinpt, 'temp', timescalbdtrspln=timescalbdtrspln)
                            
                            if r == 0:
                                gdat.listtimebrekfrst = np.copy(gdat.listtimebrek)
                                gdat.numbregibdtr = len(gdat.rflxbdtrregi)
                                gdat.indxregibdtr = np.arange(gdat.numbregibdtr)
                                gdat.indxtimeregiouttfrst = [[] for gg in gdat.indxregibdtr]
                                for kk in gdat.indxregibdtr:
                                    gdat.indxtimeregiouttfrst[kk] = np.copy(gdat.indxtimeregioutt[b][p][y][kk])
                            else:
                                if len(gdat.listtimebrek) != len(gdat.listtimebrekfrst):
                                    print('gdat.listtimebrek')
                                    print(gdat.listtimebrek)
                                    print('gdat.listtimebrekfrst')
                                    print(gdat.listtimebrekfrst)
                                    print('Number of edges changed.')
                                    raise Exception('')
                                elif gdat.boolbrekregi and ((gdat.listtimebrek[:-1] - gdat.listtimebrekfrst[:-1]) != 0.).any():
                                    print('Edges moved.')
                                    print('gdat.listtimebrek')
                                    print(gdat.listtimebrek)
                                    print('gdat.listtimebrekfrst')
                                    print(gdat.listtimebrekfrst)
                                    raise Exception('')

                            if gdat.boolplottser:
                                plot_tser_bdtr(gdat, b, p, y, z, r, strgarrybdtrinpt, strgarryclipinpt)
            
                                plot_tser(gdat, 0, p, y, strgarryclipinpt, booltoge=False)
                    
                            if gdat.typeverb > 0:
                                print('Determining outlier limits...')
                            
                            # sigma-clipping
                            lcurclip, lcurcliplowr, lcurclipuppr = scipy.stats.sigmaclip(gdat.listarrytser[strgarryclipinpt][0][p][y][:, :, 1], low=3., high=3.)
                            
                            indxtimeclipkeep = np.where((gdat.listarrytser[strgarryclipinpt][0][p][y][:, gdat.indxenerclip, 1] < lcurclipuppr) & \
                                                        (gdat.listarrytser[strgarryclipinpt][0][p][y][:, gdat.indxenerclip, 1] > lcurcliplowr))[0]
                            
                            if indxtimeclipkeep.size < 2:
                                print('No time samples left after clipping...')
                                print('gdat.listarrytser[strgarryclipinpt][0][p][y][:, gdat.indxenerclip, 1]')
                                summgene(gdat.listarrytser[strgarryclipinpt][0][p][y][:, gdat.indxenerclip, 1])
                                print('lcurcliplowr')
                                print(lcurcliplowr)
                                print('lcurclipuppr')
                                print(lcurclipuppr)
                                raise Exception('')
                            
                            #indxtimeclipmask = np.setdiff1d(np.arange(gdat.listarrytser[strgarryclipinpt][0][p][y][:, gdat.indxenerclip, 1].size), indxtimeclipkeep)
                            
                            # cluster indices of masked times
                            #listindxtimemaskclus = []
                            #for k in range(len(indxtimemask)):
                            #    if k == 0 or indxtimemask[k] != indxtimemask[k-1] + 1:
                            #        listindxtimemaskclus.append([indxtimemask[k]])
                            #    else:
                            #        listindxtimemaskclus[-1].append(indxtimemask[k])
                            #print('listindxtimemaskclus')
                            #print(listindxtimemaskclus)
                            
                            #print('Filtering clip times with index indxtimekeep into %s...' % strgarryclipoutp)
                            #gdat.listarrytser[strgarryclipoutp][0][p][y] = gdat.listarrytser['maskcust'][0][p][y][indxtimekeep, :]
                            
                            #print('Thinning the mask...')
                            #indxtimeclipmask = np.random.choice(indxtimeclipmask, size=int(indxtimeclipmask.size*0.7), replace=False)
                            
                            #print('indxtimeclipmask')
                            #summgene(indxtimeclipmask)

                            #indxtimeclipkeep = np.setdiff1d(np.arange(gdat.listarrytser[strgarryclipinpt][0][p][y][:, 1].size), indxtimeclipmask)
                            
                            indxtimekeep = indxtimekeep[indxtimeclipkeep]
                            
                            if gdat.booldiag and indxtimekeep.size < 2:
                                print('indxtimekeep')
                                print(indxtimekeep)
                                raise Exception('')

                            #boolexit = True
                            #for k in range(len(listindxtimemaskclus)):
                            #    # decrease mask

                            #    # trial detrending
                            #    bdtr_wrap(gdat, 0, p, y, gdat.epocmask, gdat.perimask, gdat.duramask, strgarrybdtrinpt, strgarryclipinpt, 'temp', timescalbdtrspln=timescalbdtrspln)
                            #    
                            #    chi2 = np.sum((gdat.listarrytser[strgarryclipinpt][0][p][y][:, 1] - gdat.listarrytser[strgarryclipinpt][0][p][y][:, 1])**2 / 
                            #                                                   gdat.listarrytser[strgarryclipinpt][0][p][y][:, 2]**2) / gdat.listarrytser[strgarryclipinpt][0][p][y][:, 1].size
                            #    if chi2 > 1.1:
                            #        boolexit = False
                            #
                            #    if gdat.boolplottser:
                            #        plot_tser(gdat, 0, p, y, strgarryclipoutp, booltoge=False)
                            
                            #if gdat.boolplottser:
                            #    plot_tser(gdat, 0, p, y, strgarrybdtroutp, booltoge=False)
                            

                            if r == gdat.maxmnumbiterbdtr - 1 or gdat.listarrytser[strgarryclipinpt][0][p][y][:, gdat.indxenerclip, 1].size == indxtimeclipkeep.size:
                                rflxtren = []
                                for kk in gdat.indxregibdtr:
                                    if gdat.typebdtr == 'gpro':
                                        rflxtren.append(gdat.listobjtspln[b][p][y][kk].predict( \
                                                                     gdat.listarrytser['maskcust'][b][p][y][gdat.indxtimeregioutt[b][p][y][kk], gdat.indxenerclip, 1], \
                                                                          t=gdat.listarrytser['maskcust'][b][p][y][:, gdat.indxenerclip, 0], \
                                                                                                                                 return_cov=False, return_var=False))
                                        
                                        #print('gdat.listindxtimeregi[b][p][y][kk]')
                                        #summgene(gdat.listindxtimeregi[b][p][y][kk])
                                        #print('gdat.indxtimeregioutt[b][p][y][kk]')
                                        #summgene(gdat.indxtimeregioutt[b][p][y][kk])
                                    
                                    if gdat.typebdtr == 'spln':
                                        rflxtren.append(gdat.listobjtspln[b][p][y][kk](gdat.listarrytser['maskcust'][b][p][y][:, gdat.indxenerclip, 0]))
                                gdat.listarrytser['bdtr'][0][p][y] = np.copy(gdat.listarrytser['maskcust'][0][p][y])
                                
                                #print('gdat.listarrytser[maskcust][0][p][y][:, gdat.indxenerclip, 1]')
                                #summgene(gdat.listarrytser['maskcust'][0][p][y][:, gdat.indxenerclip, 1])
                                #print('gdat.listarrytser[bdtr][0][p][y][:, gdat.indxenerclip, 1]')
                                #summgene(gdat.listarrytser['bdtr'][0][p][y][:, gdat.indxenerclip, 1])
                                #print('np.concatenate(rflxtren)')
                                #summgene(np.concatenate(rflxtren))
                                
                                gdat.listarrytser['bdtr'][0][p][y][:, gdat.indxenerclip, 1] = \
                                                1. + gdat.listarrytser['maskcust'][0][p][y][:, gdat.indxenerclip, 1] - np.concatenate(rflxtren)
                            
                                if r == gdat.maxmnumbiterbdtr - 1:
                                    print('Maximum number of trial detrending iterations attained. Breaking the loop...')
                                if gdat.listarrytser[strgarryclipinpt][0][p][y][:, gdat.indxenerclip, 1].size == indxtimeclipkeep.size:
                                    print('No more clipping is needed. Breaking the loop...')
                                if gdat.typeverb > 0:
                                    print('')
                                    print('')
                                
                                break
                                
                            else:
                                # plot the trial detrended and sigma-clipped time-series data
                                #print('strgarrybdtroutp')
                                #print(strgarrybdtroutp)
                                #if gdat.boolplottser:
                                #    plot_tser(gdat, 0, p, y, strgarryclipoutp, booltoge=False)
                                r += 1
                            
                                if gdat.typeverb > 0:
                                    print('')
                                    print('')

                        #gdat.numbiterbdtr[p][y] = r
                        #bdtr_wrap(gdat, 0, p, y, gdat.epocmask, gdat.perimask, gdat.duramask, strgarryclipoutp, strgarrybdtroutp, strgarrybdtrblin, timescalbdtrspln=timescalbdtrspln)
                        
                        #gdat.listarrytser[strgarrybdtr][0][p][y] = gdat.listarrytser[strgarrybdtroutp][0][p][y]
            
            if gdat.listtimescalbdtrspln[0] == 0.:
                gdat.listarrytser['bdtr'] = gdat.listarrytser['maskcust']

            # merge chunks
            for p in gdat.indxinst[0]:
                gdat.arrytser['bdtr'][0][p] = np.concatenate(gdat.listarrytser['bdtr'][0][p], 0)
            
            # write baseline-detrended light curve
            for p in gdat.indxinst[0]:
                
                for e in gdat.indxener:

                    if gdat.numbchun[0][p] > 1:
                        path = gdat.pathdatatarg + 'arrytserbdtr%s%s.csv' % (gdat.liststrginst[0][p], gdat.liststrgener[e])
                        if not os.path.exists(path):
                            if gdat.typeverb > 0:
                                print('Writing to %s...' % path)
                            np.savetxt(path, gdat.arrytser['bdtr'][0][p][:, e, :], delimiter=',', \
                                                            header='time,%s,%s_err' % (gdat.liststrgtseralle[0], gdat.liststrgtseralle[0]))
                    
                    for y in gdat.indxchun[0][p]:
                        path = gdat.pathdatatarg + 'arrytserbdtr%s%s%s.csv' % (gdat.liststrginst[0][p], gdat.liststrgchun[0][p][y], gdat.liststrgener[e])
                        if not os.path.exists(path):
                            if gdat.typeverb > 0:
                                print('Writing to %s...' % path)
                            np.savetxt(path, gdat.listarrytser['bdtr'][0][p][y][:, e, :], delimiter=',', \
                                                           header='time,%s,%s_err' % (gdat.liststrgtseralle[0], gdat.liststrgtseralle[0]))
        
            if gdat.boolplottser:
                for p in gdat.indxinst[0]:
                    for y in gdat.indxchun[0][p]:
                        plot_tser(gdat, 0, p, y, 'bdtr')
                    plot_tser(gdat, 0, p, None, 'bdtr')
        
        else:
            gdat.arrytser['bdtr'] = gdat.arrytser['maskcust']
            gdat.listarrytser['bdtr'] = gdat.listarrytser['maskcust']
        
        if gdat.booldiag:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    if len(gdat.arrytser['bdtr'][b][p]) == 0:
                        raise Exception('')

        # update the time axis
        gdat.listtime = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.listtimefine = [[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.timeconc = [[] for b in gdat.indxdatatser]
        gdat.timefineconc = [[] for b in gdat.indxdatatser]
        gdat.time = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.timefine = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                gdat.time[b][p] = gdat.arrytser['bdtr'][b][p][:, 0, 0]
                for y in gdat.indxchun[b][p]:
                    gdat.listtime[b][p][y] = gdat.listarrytser['bdtr'][b][p][y][:, 0, 0]
                    difftimefine = 0.5 * np.amin(gdat.listtime[b][p][y][1:] - gdat.listtime[b][p][y][:-1])
                    gdat.listtimefine[b][p][y] = np.arange(np.amin(gdat.listtime[b][p][y]), np.amax(gdat.listtime[b][p][y]) + difftimefine, difftimefine)
                gdat.timefine[b][p] = np.concatenate(gdat.listtimefine[b][p])
            if len(gdat.time[b]) > 0:
                gdat.timeconc[b] = np.concatenate(gdat.time[b])
                gdat.timefineconc[b] = np.concatenate(gdat.timefine[b])

        # sampling rate
        ## temporal
        gdat.ratesamptime = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                gdat.ratesamptime[b][p] = np.amin(gdat.timeconc[0][1:] - gdat.timeconc[0][:-1])
        if gdat.numbener > 1:
            gdat.ratesampener = np.amin(gdat.listener[1:] - gdat.listener[:-1])
        
        # rebinning
        gdat.numbrebn = 50
        gdat.indxrebn = np.arange(gdat.numbrebn)
        gdat.listdeltrebn = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                gdat.minmdeltrebn = max(100. * gdat.ratesamptime[b][p], 0.1 * 0.3 * (gdat.timeconc[0][-1] - gdat.timeconc[0][0]))
                gdat.maxmdeltrebn =  0.3 * (gdat.timeconc[0][-1] - gdat.timeconc[0][0])
                gdat.listdeltrebn[b][p] = np.linspace(gdat.minmdeltrebn, gdat.maxmdeltrebn, gdat.numbrebn)
        
        # search for periodic boxes
        if gdat.boolsrchpbox:
            
            # temp
            for p in gdat.indxinst[0]:
                
                # input data to the periodic box search pipeline
                arry = np.copy(gdat.arrytser['bdtr'][0][p][:, 0, :])
                
                if gdat.dictpboxinpt is None:
                    gdat.dictpboxinpt = dict()
                
                if not 'typeverb' in gdat.dictpboxinpt:
                    gdat.dictpboxinpt['typeverb'] = gdat.typeverb
                
                if not 'pathimag' in gdat.dictpboxinpt:
                    if gdat.boolplot:
                        gdat.dictpboxinpt['pathimag'] = gdat.pathimagtarg
                
                if not 'boolsrchposi' in gdat.dictpboxinpt:
                    if 'cosc' in gdat.listtypeanls:
                        gdat.dictpboxinpt['boolsrchposi'] = True
                    else:
                        gdat.dictpboxinpt['boolsrchposi'] = False
                gdat.dictpboxinpt['pathdata'] = gdat.pathdatatarg
                gdat.dictpboxinpt['timeoffs'] = gdat.timeoffs
                gdat.dictpboxinpt['strgextn'] = '%s_%s' % (gdat.liststrginst[0][p], gdat.strgtarg)
                gdat.dictpboxinpt['typefileplot'] = gdat.typefileplot
                gdat.dictpboxinpt['figrsizeydobskin'] = gdat.figrsizeydobskin
                gdat.dictpboxinpt['alphraww'] = gdat.alphraww

                dictpboxoutp = ephesus.srch_pbox(arry, **gdat.dictpboxinpt)
                
                gdat.dictmileoutp['dictpboxoutp'] = dictpboxoutp
                
                if gdat.epocmtracompprio is None:
                    gdat.epocmtracompprio = dictpboxoutp['epocmtracomp']
                if gdat.pericompprio is None:
                    gdat.pericompprio = dictpboxoutp['pericomp']
                gdat.deptprio = 1. - 1e-3 * dictpboxoutp['depttrancomp']
                gdat.duraprio = dictpboxoutp['duracomp']
                gdat.cosicompprio = np.zeros_like(dictpboxoutp['epocmtracomp']) 
                gdat.rratcompprio = np.sqrt(1e-3 * gdat.deptprio)
                gdat.rsmacompprio = np.sin(np.pi * gdat.duraprio / gdat.pericompprio / 24.)
                
                gdat.perimask = gdat.pericompprio
                gdat.epocmask = gdat.epocmtracompprio
                gdat.duramask = 2. * gdat.duraprio
        
        if gdat.typeverb > 0:
            print('gdat.epocmask')
            print(gdat.epocmask)
            print('gdat.perimask')
            print(gdat.perimask)
            print('gdat.duramask')
            print(gdat.duramask)
        
        # search for flares
        if gdat.boolsrchflar:
            dictsrchflarinpt['pathimag'] = gdat.pathimagtarg
            
            gdat.listindxtimeflar = [[[] for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]]
            gdat.listmdetflar = [[[] for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]]
            gdat.precphot = [np.empty(gdat.numbchun[0][p]) for p in gdat.indxinst[0]]
            gdat.thrsrflxflar = [np.empty(gdat.numbchun[0][p]) for p in gdat.indxinst[0]]
            for p in gdat.indxinst[0]:
                for y in gdat.indxchun[0][0]:
                    
                    if gdat.typemodlflar == 'outl':
                        listydat = gdat.listarrytser['bdtr'][0][p][y][:, 1]
                        medi = np.median(listydat)
                        indxcent = np.where((listydat > np.percentile(listydat, 1.)) & (listydat < np.percentile(listydat, 99.)))[0]
                        stdv = np.std(listydat[indxcent])
                        gdat.precphot[p][y] = stdv
                        listmdetflar = (listydat - medi) / stdv
                        gdat.thrsrflxflar[p][y] = medi + stdv * gdat.thrssigmflar
                        indxtimeposi = np.where(listmdetflar > gdat.thrssigmflar)[0]
                        
                        for n in range(len(indxtimeposi)):
                            if (n == len(indxtimeposi) - 1) or (n < len(indxtimeposi) - 1) and not ((indxtimeposi[n] + 1) in indxtimeposi):
                                gdat.listindxtimeflar[p][y].append(indxtimeposi[n])
                                mdetflar = listmdetflar[indxtimeposi[n]]
                                gdat.listmdetflar[p][y].append(mdetflar)
                        gdat.listindxtimeflar[p][y] = np.array(gdat.listindxtimeflar[p][y])
                        gdat.listmdetflar[p][y] = np.array(gdat.listmdetflar[p][y])

                    if gdat.typemodlflar == 'tmpl':
                        dictsrchflaroutp = ephesus.srch_flar(gdat.arrytser['bdtr'][0][p][:, 0], gdat.arrytser['bdtr'][0][p][:, 1], **dictsrchflarinpt)
                
            gdat.dictmileoutp['listindxtimeflar'] = gdat.listindxtimeflar
            gdat.dictmileoutp['listmdetflar'] = gdat.listmdetflar
            gdat.dictmileoutp['precphot'] = gdat.precphot
            
            gdat.arrytser['flar'] = [[[] for p in gdat.indxinst[0]] for b in gdat.indxdatatser]
            gdat.listarrytser['flar'] = [[[[] for y in gdat.indxchun[0][p]] for p in gdat.indxinst[0]] for b in gdat.indxdatatser]
            for p in gdat.indxinst[0]:
                for y in gdat.indxchun[0][p]:
                    if gdat.boolplottser:
                        plot_tser(gdat, 0, p, y, 'flar')
                if gdat.boolplottser:
                    plot_tser(gdat, 0, p, None, 'flar')
            
            if gdat.typeverb > 0:
                print('temp: skipping masking out of flaress...')
            # mask out flares
            #numbkern = len(maxmcorr)
            #indxkern = np.arange(numbkern)
            #listindxtimemask = []
            #for k in indxkern:
            #    for indxtime in gdat.listindxtimeposimaxm[k]:
            #        indxtimemask = np.arange(indxtime - 60, indxtime + 60)
            #        listindxtimemask.append(indxtimemask)
            #indxtimemask = np.concatenate(listindxtimemask)
            #indxtimemask = np.unique(indxtimemask)
            #indxtimegood = np.setdiff1d(np.arange(gdat.time.size), indxtimemask)
            #gdat.time = gdat.time[indxtimegood]
            #gdat.lcurdata = gdat.lcurdata[indxtimegood]
            #gdat.lcurdatastdv = gdat.lcurdatastdv[indxtimegood]
            #gdat.numbtime = gdat.time.size

    if gdat.boolmodltran:
        gdat.numbcomp = gdat.epocmtracompprio.size
    else:
        gdat.numbcomp = 0
    
    if gdat.typeverb > 0:
        print('gdat.numbcomp')
        print(gdat.numbcomp)
    
    gdat.fitt.indxcomp = np.arange(gdat.numbcomp)
     
    # data validation (DV) report
    ## number of pages in the DV report
    if gdat.boolplot:
        gdat.numbpage = gdat.numbcomp + 1
        gdat.indxpage = np.arange(gdat.numbpage)
        for j in gdat.fitt.indxcomp:
            gdat.listdictdvrp.append([])
    
        # add pbox plots to the DV report
        if gdat.boolsrchpbox and gdat.boolplot:
            for p in gdat.indxinst[0]:
                for g, name in enumerate(['sigr', 'resisigr', 'stdvresisigr', 'sdeecomp', 'pcur', 'rflx']):
                    for j in range(len(dictpboxoutp['epocmtracomp'])):
                        gdat.listdictdvrp[j+1].append({'path': dictpboxoutp['listpathplot%s' % name][j], 'limt':[0., 0.9 - g * 0.1, 0.5, 0.1]})
    
    gdat.dictmileoutp['numbcomp'] = gdat.numbcomp
    
    if gdat.booltrancomp is None:
        if gdat.boolmodltran:
            gdat.booltrancomp = np.zeros(gdat.numbcomp, dtype=bool)
            gdat.booltrancomp[np.where(np.isfinite(gdat.deptprio))] = True

    if gdat.booltserdata:
        # concatenate time-series data from different instruments
        gdat.arrytsertotl = [[] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            if gdat.numbinst[b] > 0:
                gdat.arrytsertotl[b] = np.concatenate(gdat.arrytser['raww'][b], axis=0)
        gdat.dictmileoutp['arrytsertotl'] = gdat.arrytsertotl
        
    # calculate LS periodogram
    if gdat.boolcalclspe:
        if gdat.boolplot:
            pathimaglspe = gdat.pathimagtarg
        else:
            pathimaglspe = None

        liststrgarrylspe = ['raww']
        if gdat.boolbdtr:
            liststrgarrylspe += ['bdtr']
        for b in gdat.indxdatatser:
            
            # temp -- neglects LS periodograms of RV data
            if b == 1:
                continue
            
            if gdat.numbinst[b] > 0:
                
                for e in gdat.indxener:
                    if gdat.numbinst[b] > 1:
                        strgextn = '%s%s' % (gdat.liststrgtser[b], gdat.liststrgener[e])
                        gdat.dictlspeoutp = ephesus.exec_lspe(gdat.arrytsertotl[b][:, e, :], pathimag=pathimaglspe, strgextn=strgextn, maxmfreq=maxmfreqlspe, \
                                                                                  typeverb=gdat.typeverb, typefileplot=gdat.typefileplot, pathdata=gdat.pathdatatarg)
                    
                    for p in gdat.indxinst[b]:
                        for strg in liststrgarrylspe:
                            strgextn = '%s_%s_%s%s' % (strg, gdat.liststrgtser[b], gdat.liststrginst[b][p], gdat.liststrgener[e]) 
                            gdat.dictlspeoutp = ephesus.exec_lspe(gdat.arrytser[strg][b][p][:, e, :], pathimag=pathimaglspe, strgextn=strgextn, maxmfreq=maxmfreqlspe, \
                                                                                  typeverb=gdat.typeverb, typefileplot=gdat.typefileplot, pathdata=gdat.pathdatatarg)
        
                    gdat.dictmileoutp['perilspempow'] = gdat.dictlspeoutp['perimpow']
                    gdat.dictmileoutp['powrlspempow'] = gdat.dictlspeoutp['powrmpow']
                    
                    if gdat.boolplot:
                        gdat.listdictdvrp[0].append({'path': gdat.dictlspeoutp['pathplot'], 'limt':[0., 0.8, 0.5, 0.1]})
        
    if gdat.boolmodltran:
        if gdat.liststrgcomp is None:
            gdat.liststrgcomp = ephesus.retr_liststrgcomp(gdat.numbcomp)
        if gdat.listcolrcomp is None:
            gdat.listcolrcomp = ephesus.retr_listcolrcomp(gdat.numbcomp)
        
        if gdat.typeverb > 0:
            print('Planet letters: ')
            print(gdat.liststrgcomp)
    
        if gdat.duraprio is None:
            
            if gdat.booldiag and (gdat.pericompprio is None or gdat.rsmacompprio is None or gdat.cosicompprio is None):
                print('gdat.pericompprio')
                print(gdat.pericompprio)
                print('gdat.rsmacompprio')
                print(gdat.rsmacompprio)
                print('gdat.cosicompprio')
                print(gdat.cosicompprio)
                raise Exception('')

            gdat.duraprio = ephesus.retr_duratran(gdat.pericompprio, gdat.rsmacompprio, gdat.cosicompprio)
        
        if gdat.rratcompprio is None:
            gdat.rratcompprio = np.sqrt(1e-3 * gdat.deptprio)
        if gdat.rsmacompprio is None:
            gdat.rsmacompprio = np.sqrt(np.sin(np.pi * gdat.duraprio / gdat.pericompprio / 24.)**2 + gdat.cosicompprio**2)
        if gdat.ecoscompprio is None:
            gdat.ecoscompprio = np.zeros(gdat.numbcomp)
        if gdat.esincompprio is None:
            gdat.esincompprio = np.zeros(gdat.numbcomp)
        if gdat.rvelsemaprio is None:
            gdat.rvelsemaprio = np.zeros(gdat.numbcomp)
        
        if gdat.stdvrratcompprio is None:
            gdat.stdvrratcompprio = 0.01 + np.zeros(gdat.numbcomp)
        if gdat.stdvrsmacompprio is None:
            gdat.stdvrsmacompprio = 0.01 + np.zeros(gdat.numbcomp)
        if gdat.stdvepocmtracompprio is None:
            gdat.stdvepocmtracompprio = 0.1 + np.zeros(gdat.numbcomp)
        if gdat.stdvpericompprio is None:
            gdat.stdvpericompprio = 0.01 + np.zeros(gdat.numbcomp)
        if gdat.stdvcosicompprio is None:
            gdat.stdvcosicompprio = 0.05 + np.zeros(gdat.numbcomp)
        if gdat.stdvecoscompprio is None:
            gdat.stdvecoscompprio = 0.1 + np.zeros(gdat.numbcomp)
        if gdat.stdvesincompprio is None:
            gdat.stdvesincompprio = 0.1 + np.zeros(gdat.numbcomp)
        if gdat.stdvrvelsemaprio is None:
            gdat.stdvrvelsemaprio = 0.001 + np.zeros(gdat.numbcomp)
        
        # others
        if gdat.projoblqprio is None:
            gdat.projoblqprio = 0. + np.zeros(gdat.numbcomp)
        if gdat.stdvprojoblqprio is None:
            gdat.stdvprojoblqprio = 10. + np.zeros(gdat.numbcomp)
        
        # order planets with respect to period
        if gdat.typepriocomp != 'inpt':
            
            if gdat.typeverb > 0:
                print('Sorting the planets with respect to orbital period...')
            
            indxcompsort = np.argsort(gdat.pericompprio)
            
            gdat.booltrancomp = gdat.booltrancomp[indxcompsort]
            gdat.rratcompprio = gdat.rratcompprio[indxcompsort]
            gdat.rsmacompprio = gdat.rsmacompprio[indxcompsort]
            gdat.epocmtracompprio = gdat.epocmtracompprio[indxcompsort]
            gdat.pericompprio = gdat.pericompprio[indxcompsort]
            gdat.cosicompprio = gdat.cosicompprio[indxcompsort]
            gdat.ecoscompprio = gdat.ecoscompprio[indxcompsort]
            gdat.esincompprio = gdat.esincompprio[indxcompsort]
            gdat.rvelsemaprio = gdat.rvelsemaprio[indxcompsort]
        
            gdat.duraprio = gdat.duraprio[indxcompsort]
        
        # if stellar features are NaN, use Solar defaults
        for featstar in gdat.listfeatstar:
            if not hasattr(gdat, featstar) or getattr(gdat, featstar) is None or not np.isfinite(getattr(gdat, featstar)):
                if featstar == 'radistar':
                    setattr(gdat, featstar, 1.)
                if featstar == 'massstar':
                    setattr(gdat, featstar, 1.)
                if featstar == 'tmptstar':
                    setattr(gdat, featstar, 5778.)
                if featstar == 'vsiistar':
                    setattr(gdat, featstar, 1e3)
                if gdat.typeverb > 0:
                    print('Setting %s to the Solar value!' % featstar)

        # if stellar feature uncertainties are NaN, use 10%
        for featstar in gdat.listfeatstar:
            if (not hasattr(gdat, 'stdv' + featstar) or getattr(gdat, 'stdv' + featstar) is None or not np.isfinite(getattr(gdat, 'stdv' + featstar))) \
                                                                        and not (featstar == 'rascstar' or featstar == 'declstar'):
                setattr(gdat, 'stdv' + featstar, 0.5 * getattr(gdat, featstar))
                if gdat.typeverb > 0:
                    print('Setting %s uncertainty to 50%%!' % featstar)

        gdat.radicompprio = gdat.rratcompprio * gdat.radistar
        
        if gdat.typeverb > 0:
            
            if ('psys' in gdat.listtypemodl or 'psyspcur' in gdat.listtypemodl):
                print('Stellar priors:')
                print('gdat.rascstar')
                print(gdat.rascstar)
                print('gdat.declstar')
                print(gdat.declstar)
                print('gdat.radistar [R_S]')
                print(gdat.radistar)
                print('gdat.stdvradistar [R_S]')
                print(gdat.stdvradistar)
                print('gdat.massstar')
                print(gdat.massstar)
                print('gdat.stdvmassstar')
                print(gdat.stdvmassstar)
                print('gdat.vsiistar')
                print(gdat.vsiistar)
                print('gdat.stdvvsiistar')
                print(gdat.stdvvsiistar)
                print('gdat.massstar [M_S]')
                print(gdat.massstar)
                print('gdat.stdvmassstar [M_S]')
                print(gdat.stdvmassstar)
                print('gdat.tmptstar')
                print(gdat.tmptstar)
                print('gdat.stdvtmptstar')
                print(gdat.stdvtmptstar)
                
                print('Planetary priors:')
                print('gdat.duraprio')
                print(gdat.duraprio)
                print('gdat.deptprio')
                print(gdat.deptprio)
                print('gdat.rratcompprio')
                print(gdat.rratcompprio)
                print('gdat.rsmacompprio')
                print(gdat.rsmacompprio)
                print('gdat.epocmtracompprio')
                print(gdat.epocmtracompprio)
                print('gdat.pericompprio')
                print(gdat.pericompprio)
                print('gdat.cosicompprio')
                print(gdat.cosicompprio)
                print('gdat.ecoscompprio')
                print(gdat.ecoscompprio)
                print('gdat.esincompprio')
                print(gdat.esincompprio)
                print('gdat.rvelsemaprio')
                print(gdat.rvelsemaprio)
                print('gdat.stdvrratcompprio')
                print(gdat.stdvrratcompprio)
                print('gdat.stdvrsmacompprio')
                print(gdat.stdvrsmacompprio)
                print('gdat.stdvepocmtracompprio')
                print(gdat.stdvepocmtracompprio)
                print('gdat.stdvpericompprio')
                print(gdat.stdvpericompprio)
                print('gdat.stdvcosicompprio')
                print(gdat.stdvcosicompprio)
                print('gdat.stdvecoscompprio')
                print(gdat.stdvecoscompprio)
                print('gdat.stdvesincompprio')
                print(gdat.stdvesincompprio)
                print('gdat.stdvrvelsemaprio')
                print(gdat.stdvrvelsemaprio)
        
                if not np.isfinite(gdat.rratcompprio).all():
                    print('rrat is infinite!')
                if not np.isfinite(gdat.rsmacompprio).all():
                    print('rsma is infinite!')
                if not np.isfinite(gdat.epocmtracompprio).all():
                    print('epoc is infinite!')
                if not np.isfinite(gdat.pericompprio).all():
                    print('peri is infinite!')
                if not np.isfinite(gdat.cosicompprio).all():
                    print('cosi is infinite!')
                if not np.isfinite(gdat.ecoscompprio).all():
                    print('ecos is infinite!')
                if not np.isfinite(gdat.esincompprio).all():
                    print('esin is infinite!')
                if not np.isfinite(gdat.rvelsemaprio).all():
                    print('rvelsema is infinite!')

        # carry over RV data as is, without any detrending
        gdat.arrytser['bdtr'][1] = gdat.arrytser['raww'][1]
        gdat.listarrytser['bdtr'][1] = gdat.listarrytser['raww'][1]
        
        if gdat.booldiag:
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for y in gdat.indxchun[b][p]:
                        if len(gdat.listarrytser['bdtr'][b][p][y]) == 0:
                            print('bpy')
                            print(b, p, y)
                            raise Exception('')
            
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    if not np.isfinite(gdat.arrytser['bdtr'][b][p]).all():
                        print('b, p')
                        print(b, p)
                        indxbadd = np.where(~np.isfinite(gdat.arrytser['bdtr'][b][p]))[0]
                        print('gdat.arrytser[bdtr][b][p]')
                        summgene(gdat.arrytser['bdtr'][b][p])
                        print('indxbadd')
                        summgene(indxbadd)
                        raise Exception('')
        
        # determine times during transits
        gdat.listindxtimeoutt = [[[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser] for j in gdat.fitt.indxcomp]
        gdat.listindxtimetranindi = [[[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser] for j in gdat.fitt.indxcomp]
        gdat.listindxtimetran = [[[[[] for m in range(2)] for p in gdat.indxinst[b]] for b in gdat.indxdatatser] for j in gdat.fitt.indxcomp]
        gdat.listindxtimetranchun = [[[[[] for y in gdat.indxchun[b][p]] for p in gdat.indxinst[b]] for b in gdat.indxdatatser] for j in gdat.fitt.indxcomp]
        gdat.listindxtimeclen = [[[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser] for j in gdat.fitt.indxcomp]
        gdat.numbtimeclen = [[np.empty((gdat.numbcomp), dtype=int) for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        
        gdat.numbtran = np.empty(gdat.numbcomp, dtype=int)
        for j in gdat.fitt.indxcomp:
            gdat.listtimeconc = []
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    if not np.isfinite(gdat.duraprio[j]):
                        continue
                    # determine time mask
                    for y in gdat.indxchun[b][p]:
                        gdat.listindxtimetranchun[j][b][p][y] = ephesus.retr_indxtimetran(gdat.listarrytser['bdtr'][b][p][y][:, 0, 0], \
                                                                                               gdat.epocmtracompprio[j], gdat.pericompprio[j], gdat.duraprio[j])
                    
                    # primary
                    gdat.listindxtimetran[j][b][p][0] = ephesus.retr_indxtimetran(gdat.arrytser['bdtr'][b][p][:, 0, 0], \
                                                                                             gdat.epocmtracompprio[j], gdat.pericompprio[j], gdat.duraprio[j])
                    
                    # primary individuals
                    gdat.listindxtimetranindi[j][b][p] = ephesus.retr_indxtimetran(gdat.arrytser['bdtr'][b][p][:, 0, 0], \
                                                                                      gdat.epocmtracompprio[j], gdat.pericompprio[j], gdat.duraprio[j], boolindi=True)
                    
                    # secondary
                    gdat.listindxtimetran[j][b][p][1] = ephesus.retr_indxtimetran(gdat.arrytser['bdtr'][b][p][:, 0, 0], \
                                                                         gdat.epocmtracompprio[j], gdat.pericompprio[j], gdat.duraprio[j], boolseco=True)
                    
                    gdat.listindxtimeoutt[j][b][p] = np.setdiff1d(np.arange(gdat.arrytser['bdtr'][b][p].shape[0]), gdat.listindxtimetran[j][b][p][0])
                    
                    gdat.listtimeconc.append(gdat.arrytser['bdtr'][b][p][:, 0, 0])
            
            if len(gdat.listtimeconc) > 0:
                gdat.listtimeconc = np.concatenate(gdat.listtimeconc)
                gdat.listindxtran = ephesus.retr_indxtran(gdat.listtimeconc, gdat.epocmtracompprio[j], gdat.pericompprio[j], gdat.duraprio[j])
                gdat.numbtran[j] = len(gdat.listindxtran)

        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                for j in gdat.fitt.indxcomp:
                    # clean times for each planet
                    listindxtimetemp = []
                    for jj in gdat.fitt.indxcomp:
                        if jj != j:
                            listindxtimetemp.append(gdat.listindxtimetran[jj][b][p][0])
                    if len(listindxtimetemp) > 0:
                        listindxtimetemp = np.concatenate(listindxtimetemp)
                        listindxtimetemp = np.unique(listindxtimetemp)
                    else:
                        listindxtimetemp = np.array([])
                    gdat.listindxtimeclen[j][b][p] = np.setdiff1d(np.arange(gdat.arrytser['bdtr'][b][p].shape[0]), listindxtimetemp)
                    gdat.numbtimeclen[b][p][j] = gdat.listindxtimeclen[j][b][p].size
                    
        # ingress and egress times
        if 'psysdisktran' in gdat.listtypemodl:
            gdat.fracineg = np.zeros(2)
            gdat.listindxtimetranineg = [[[[[] for k in range(4)] for p in gdat.indxinst[b]] for b in gdat.indxdatatser] for j in gdat.fitt.indxcomp]
            gdat.durafullprio = (1. - gdat.rratcompprio) / (1. + gdat.rratcompprio) * gdat.duraprio
            for p in gdat.indxinst[0]:
                for j in gdat.fitt.indxcomp:
                    if not gdat.booltrancomp[j]:
                        continue

                    gdat.listindxtimetranineg[j][0][p][0] = ephesus.retr_indxtimetran(gdat.arrytser['bdtr'][0][p][:, 0, 0], gdat.epocmtracompprio[j], gdat.pericompprio[j], \
                                                                                                  gdat.duraprio[j], durafull=gdat.durafullprio[j], typeineg='ingrinit')
                    gdat.listindxtimetranineg[j][0][p][1] = ephesus.retr_indxtimetran(gdat.arrytser['bdtr'][0][p][:, 0, 0], gdat.epocmtracompprio[j], gdat.pericompprio[j], \
                                                                                                  gdat.duraprio[j], durafull=gdat.durafullprio[j], typeineg='ingrfinl')
                    gdat.listindxtimetranineg[j][0][p][2] = ephesus.retr_indxtimetran(gdat.arrytser['bdtr'][0][p][:, 0, 0], gdat.epocmtracompprio[j], gdat.pericompprio[j], \
                                                                                                  gdat.duraprio[j], durafull=gdat.durafullprio[j], typeineg='eggrinit')
                    gdat.listindxtimetranineg[j][0][p][3] = ephesus.retr_indxtimetran(gdat.arrytser['bdtr'][0][p][:, 0, 0], gdat.epocmtracompprio[j], gdat.pericompprio[j], \
                                                                                                  gdat.duraprio[j], durafull=gdat.durafullprio[j], typeineg='eggrfinl')
                    
                    for k in range(2):
                        indxtimefrst = gdat.listindxtimetranineg[j][0][p][2*k+0]
                        indxtimeseco = gdat.listindxtimetranineg[j][0][p][2*k+1]
                        if indxtimefrst.size == 0 or indxtimeseco.size == 0:
                            continue
                        rflxinit = np.mean(gdat.arrytser['bdtr'][0][p][indxtimefrst, 1])
                        rflxfinl = np.mean(gdat.arrytser['bdtr'][0][p][indxtimeseco, 1])
                        gdat.fracineg[k] = rflxinit / rflxfinl
                    if (gdat.fracineg == 0).any():
                        print('rflxinit')
                        print(rflxinit)
                        print('rflxfinl')
                        print(rflxfinl)
                        print('gdat.arrytser[bdtr][0][p]')
                        summgene(gdat.arrytser['bdtr'][0][p])
                        print('gdat.arrytser[bdtrnotr][0][p][:, 1]')
                        summgene(gdat.arrytser['bdtr'][0][p][:, 1])
                        print('gdat.arrytser[bdtrnotr][0][p][indxtimefrst, 1]')
                        summgene(gdat.arrytser['bdtr'][0][p][indxtimefrst, 1])
                        print('gdat.arrytser[bdtrnotr][0][p][indxtimeseco, 1]')
                        summgene(gdat.arrytser['bdtr'][0][p][indxtimeseco, 1])
                        raise Exception('')

                    path = gdat.pathdatatarg + 'fracineg%04d.csv' % j
                    np.savetxt(path, gdat.fracineg, delimiter=',')
                    gdat.dictmileoutp['fracineg%04d' % j] = gdat.fracineg
        
        if gdat.listindxchuninst is None:
            gdat.listindxchuninst = [gdat.indxchun]
    
        # plot raw data
        #if gdat.typetarg != 'inpt' and 'TESS' in gdat.liststrginst[0] and gdat.listarrytsersapp is not None:
        #    for b in gdat.indxdatatser:
        #        for p in gdat.indxinst[b]:
        #            if gdat.liststrginst[b][p] != 'TESS':
        #                continue
        #            for y in gdat.indxchun[b][p]:
        #                path = gdat.pathdatatarg + gdat.liststrgchun[b][p][y] + '_SAP.csv'
        #                if not os.path.exists(path):
        #                    if gdat.typeverb > 0:
        #                        print('Writing to %s...' % path)
        #                    np.savetxt(path, gdat.listarrytsersapp[y], delimiter=',', header='time,flux,flux_err')
        #                path = gdat.pathdatatarg + gdat.liststrgchun[b][p][y] + '_PDCSAP.csv'
        #                if not os.path.exists(path):
        #                    if gdat.typeverb > 0:
        #                        print('Writing to %s...' % path)
        #                    np.savetxt(path, gdat.listarrytserpdcc[y], delimiter=',', header='time,flux,flux_err')
        #    
        #    # plot PDCSAP and SAP light curves
        #    figr, axis = plt.subplots(2, 1, figsize=gdat.figrsizeydob)
        #    axis[0].plot(gdat.arrytsersapp[:, 0] - gdat.timeoffs, gdat.arrytsersapp[:, 1], color='k', marker='.', ls='', ms=1, rasterized=True)
        #    axis[1].plot(gdat.arrytserpdcc[:, 0] - gdat.timeoffs, gdat.arrytserpdcc[:, 1], color='k', marker='.', ls='', ms=1, rasterized=True)
        #    #axis[0].text(.97, .97, 'SAP', transform=axis[0].transAxes, size=20, color='r', ha='right', va='top')
        #    #axis[1].text(.97, .97, 'PDC', transform=axis[1].transAxes, size=20, color='r', ha='right', va='top')
        #    axis[1].set_xlabel('Time [BJD - %d]' % gdat.timeoffs)
        #    for a in range(2):
        #        axis[a].set_ylabel(gdat.labltserphot)
        #    
        #    plt.subplots_adjust(hspace=0.)
        #    path = gdat.pathimagtarg + 'lcurspoc_%s.%s' % (gdat.strgtarg, gdat.typefileplot)
        #    gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0.4, 0.05, 0.8, 0.8]})
        #    if gdat.typeverb > 0:
        #        print('Writing to %s...' % path)
        #    plt.savefig(path)
        #    plt.close()
        
    # calculate the visibility of the target
    if gdat.boolcalcvisi:
        
        if gdat.listdelttimeobvtyear is None:
            gdat.listdelttimeobvtyear = np.linspace(0., 365., 10000)

        massairr = tdpy.calc_visitarg(gdat.rasctarg, gdat.decltarg, gdat.latiobvt, gdat.longobvt, gdat.strgtimeobvtyear, gdat.listdelttimeobvtyear, gdat.heigobvt)

        gdat.dictmileoutp['massairr'] = massairr

        # alt-az coordinate object for the Sun
        #objtcoorsunnalazyear = astropy.coordinates.get_sun(objttimeyear)
        #objtcoorsunnalazyear = objtcoorsunnalazyear.transform_to(objtframobvtyear)
            
        # quantities during a given night
        if gdat.strgtimeobvtnigh is not None:
            objttimenigh = astropy.time.Time(astropy.time.Time(gdat.strgtimeobvtnigh).jd, format='jd', location=objtlocaobvt)
            objttimenighcent = astropy.time.Time(int(objttimenigh.jd), format='jd', location=objtlocaobvt)
            objttimenighcen1 = astropy.time.Time(int(objttimenigh.jd + 1), format='jd', location=objtlocaobvt)
            objttimenigh = objttimenighcent + (12. + timedelt - gdat.offstimeobvt) * astropy.units.hour
        
            # frame object for the observatory during the selected night
            objtframobvtnigh = astropy.coordinates.AltAz(obstime=objttimenigh, location=objtlocaobvt)
        
            # alt-az coordinate object for the Sun
            objtcoorsunnalaznigh = astropy.coordinates.get_sun(objttimenigh).transform_to(objtframobvtnigh)
            # alt-az coordinate object for the Moon
            objtcoormoonalaznigh = astropy.coordinates.get_moon(objttimenigh).transform_to(objtframobvtnigh)
            # alt-az coordinate object for the target
            objtcoorplanalaznigh = astropy.coordinates.SkyCoord(ra=gdat.rasctarg, dec=gdat.decltarg, frame='icrs', unit='deg').transform_to(objtframobvtnigh)
        
            # air mass of the target during the night
            massairr = objtcoorplanalaznigh.secz
        
            for j in gdat.fitt.indxcomp:
                indx = ephesus.retr_indxtimetran(timeyear, gdat.epocmtracompprio[j], gdat.pericompprio[j], gdat.duraprio[j])
                
                import operator
                import itertools
                for k, g in itertools.groupby(enumerate(list(indx)), lambda ix : ix[0] - ix[1]):
                    print(map(operator.itemgetter(1), g))
            
            labltime = 'Local time to Midnight [hour]'
            print('%s, Air mass' % labltime)
            for ll in range(len(massairr)):
                print('%6g %6.3g' % (timedelt[ll], massairr[ll]))

            
    # plot visibility of the target
    if gdat.boolplotvisi:
        strgtitl = '%s, %s/%s' % (gdat.labltarg, objttimenighcent.iso[:10], objttimenighcen1.iso[:10])

        # plot air mass
        figr, axis = plt.subplots(figsize=(8, 4))
        
        indx = np.where(np.isfinite(massairr) & (massairr > 0))[0]
        plt.plot(timedelt[indx], massairr[indx])
        axis.fill_between(timedelt, 0, 90, objtcoorsunnalaznigh.alt < -0*astropy.units.deg, color='0.5', zorder=0)
        axis.fill_between(timedelt, 0, 90, objtcoorsunnalaznigh.alt < -18*astropy.units.deg, color='k', zorder=0)
        axis.fill_between(timedelt, 0, 90, (massairr > 2.) | (massairr < 1.), color='r', alpha=0.3, zorder=0)
        axis.set_xlabel(labltime)
        axis.set_ylabel('Airmass')
        limtxdat = [np.amin(timedelt), np.amax(timedelt)]
        axis.set_title(strgtitl)
        axis.set_xlim(limtxdat)
        axis.set_ylim([1., 2.])
        path = gdat.pathimagtarg + 'airmass_%s.%s' % (gdat.strgtarg, gdat.typefileplot)
        print('Writing to %s...' % path)
        plt.savefig(path)
        
        # plot altitude
        figr, axis = plt.subplots(figsize=(8, 4))
        axis.plot(timedelt, objtcoorsunnalaznigh.alt, color='orange', label='Sun')
        axis.plot(timedelt, objtcoormoonalaznigh.alt, color='gray', label='Moon')
        axis.plot(timedelt, objtcoorplanalaznigh.alt, color='blue', label=gdat.labltarg)
        axis.fill_between(timedelt, 0, 90, objtcoorsunnalaznigh.alt < -0*astropy.units.deg, color='0.5', zorder=0)
        axis.fill_between(timedelt, 0, 90, objtcoorsunnalaznigh.alt < -18*astropy.units.deg, color='k', zorder=0)
        axis.fill_between(timedelt, 0, 90, (massairr > 2.) | (massairr < 1.), color='r', alpha=0.3, zorder=0)
        axis.legend(loc='upper left')
        plt.ylim([0, 90])
        axis.set_title(strgtitl)
        axis.set_xlim(limtxdat)
        axis.set_xlabel(labltime)
        axis.set_ylabel('Altitude [deg]')
        
        path = gdat.pathimagtarg + 'altitude_%s.%s' % (gdat.strgtarg, gdat.typefileplot)
        print('Writing to %s...' % path)
        plt.savefig(path)

    ### bin the light curve
    if gdat.booltserdata:
        pass
        #gdat.delttimebind = 1. # [days]
        #for b in gdat.indxdatatser:
        #    for p in gdat.indxinst[b]:
        #        gdat.arrytser['bdtrbind'][b][p] = ephesus.rebn_tser(gdat.arrytser['bdtr'][b][p], delt=gdat.delttimebind)
        #        for y in gdat.indxchun[b][p]:
        #            gdat.listarrytser['bdtrbind'][b][p][y] = ephesus.rebn_tser(gdat.listarrytser['bdtr'][b][p][y], delt=gdat.delttimebind)
        #            
        #            path = gdat.pathdatatarg + 'arrytserbdtrbind%s%s.csv' % (gdat.liststrginst[b][p], gdat.liststrgchun[b][p][y])
        #            if not os.path.exists(path):
        #                if gdat.typeverb > 0:
        #                    print('Writing to %s' % path)
        #                np.savetxt(path, gdat.listarrytser['bdtrbind'][b][p][y], delimiter=',', \
        #                                                header='time,%s,%s_err' % (gdat.liststrgtseralle[b], gdat.liststrgtseralle[b]))
        #        
        #            if gdat.boolplottser:
        #                plot_tser(gdat, b, p, y, 'bdtrbind')
                
    

    gdat.dictmileoutp['boolposianls'] = np.empty(gdat.numbtypeposi, dtype=bool)
    if gdat.boolsrchpbox:
        gdat.dictmileoutp['boolposianls'][0] = dictpboxoutp['sdeecomp'][0] > gdat.thrssdeecosc
    if gdat.boolcalclspe:
        gdat.dictmileoutp['boolposianls'][1] = gdat.dictmileoutp['powrlspempow'] > gdat.thrslspecosc
    gdat.dictmileoutp['boolposianls'][2] = gdat.dictmileoutp['boolposianls'][0] or gdat.dictmileoutp['boolposianls'][1]
    gdat.dictmileoutp['boolposianls'][3] = gdat.dictmileoutp['boolposianls'][0] and gdat.dictmileoutp['boolposianls'][1]
                    
    if gdat.booltserdata:
        if gdat.boolmodlpcur:
            ### Doppler beaming
            if gdat.typeverb > 0:
                print('temp: check Doppler beaming predictions.')
            gdat.binswlenbeam = np.linspace(0.6, 1., 101)
            gdat.meanwlenbeam = (gdat.binswlenbeam[1:] + gdat.binswlenbeam[:-1]) / 2.
            gdat.diffwlenbeam = (gdat.binswlenbeam[1:] - gdat.binswlenbeam[:-1]) / 2.
            x = 2.248 / gdat.meanwlenbeam
            gdat.funcpcurmodu = .25 * x * np.exp(x) / (np.exp(x) - 1.)
            gdat.consbeam = np.sum(gdat.diffwlenbeam * gdat.funcpcurmodu)

            #if ''.join(gdat.liststrgcomp) != ''.join(sorted(gdat.liststrgcomp)):
            #if gdat.typeverb > 0:
            #       print('Provided planet letters are not in order. Changing the TCE order to respect the letter order in plots (b, c, d, e)...')
            #    gdat.fitt.indxcomp = np.argsort(np.array(gdat.liststrgcomp))

    gdat.liststrgcompfull = np.empty(gdat.numbcomp, dtype='object')
    for j in gdat.fitt.indxcomp:
        gdat.liststrgcompfull[j] = gdat.labltarg + ' ' + gdat.liststrgcomp[j]

    ## augment object dictinary
    gdat.dictfeatobjt = dict()
    gdat.dictfeatobjt['namestar'] = np.array([gdat.labltarg] * gdat.numbcomp)
    gdat.dictfeatobjt['nameplan'] = gdat.liststrgcompfull
    # temp
    gdat.dictfeatobjt['booltran'] = np.array([True] * gdat.numbcomp, dtype=bool)
    gdat.dictfeatobjt['vmagsyst'] = np.zeros(gdat.numbcomp) + gdat.vmagsyst
    gdat.dictfeatobjt['jmagsyst'] = np.zeros(gdat.numbcomp) + gdat.jmagsyst
    gdat.dictfeatobjt['hmagsyst'] = np.zeros(gdat.numbcomp) + gdat.hmagsyst
    gdat.dictfeatobjt['kmagsyst'] = np.zeros(gdat.numbcomp) + gdat.kmagsyst
    gdat.dictfeatobjt['numbplanstar'] = np.zeros(gdat.numbcomp) + gdat.numbcomp
    gdat.dictfeatobjt['numbplantranstar'] = np.zeros(gdat.numbcomp) + gdat.numbcomp
    
    if gdat.booltserdata:
        if gdat.boolmodlpcur:
            if gdat.dilu == 'lygos':
                if gdat.typeverb > 0:
                    print('Calculating the contamination ratio...')
                gdat.contrati = lygos.retr_contrati()

            # correct for dilution
            #if gdat.typeverb > 0:
            #print('Correcting for dilution!')
            #if gdat.dilucorr is not None:
            #    gdat.arrytserdilu = np.copy(gdat.listarrytser['bdtr'][b][p][y])
            #if gdat.dilucorr is not None:
            #    gdat.arrytserdilu[:, 1] = 1. - gdat.dilucorr * (1. - gdat.listarrytser['bdtr'][b][p][y][:, 1])
            #gdat.arrytserdilu[:, 1] = 1. - gdat.contrati * gdat.contrati * (1. - gdat.listarrytser['bdtr'][b][p][y][:, 1])
            
            ## phase-fold and save the baseline-detrended light curve
            gdat.numbbinspcurtotl = 100
            gdat.delttimebindzoom = gdat.duraprio / 24. / 50.
            gdat.arrypcur = dict()

            gdat.arrypcur['quadbdtr'] = [[[[] for j in gdat.fitt.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            gdat.arrypcur['quadbdtrbindtotl'] = [[[[] for j in gdat.fitt.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            gdat.arrypcur['primbdtr'] = [[[[] for j in gdat.fitt.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            gdat.arrypcur['primbdtrbindtotl'] = [[[[] for j in gdat.fitt.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            gdat.arrypcur['primbdtrbindzoom'] = [[[[] for j in gdat.fitt.indxcomp] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
            gdat.liststrgpcur = ['bdtr', 'resi', 'modl']
            gdat.liststrgpcurcomp = ['modltotl', 'modlstel', 'modlplan', 'modlelli', 'modlpmod', 'modlnigh', 'modlbeam', 'bdtrplan']
            gdat.binsphasprimtotl = np.linspace(-0.5, 0.5, gdat.numbbinspcurtotl + 1)
            gdat.binsphasquadtotl = np.linspace(-0.25, 0.75, gdat.numbbinspcurtotl + 1)
            gdat.numbbinspcurzoom = (gdat.pericompprio / gdat.delttimebindzoom).astype(int)
            gdat.binsphasprimzoom = [[] for j in gdat.fitt.indxcomp]
            for j in gdat.fitt.indxcomp:
                if np.isfinite(gdat.duraprio[j]):
                    gdat.binsphasprimzoom[j] = np.linspace(-0.5, 0.5, gdat.numbbinspcurzoom[j] + 1)

            if gdat.typeverb > 0:
                print('Phase folding and binning the light curve...')
            for b in gdat.indxdatatser:
                for p in gdat.indxinst[b]:
                    for j in gdat.fitt.indxcomp:

                        gdat.arrypcur['primbdtr'][b][p][j] = ephesus.fold_tser(gdat.arrytser['bdtr'][b][p][gdat.listindxtimeclen[j][b][p], :], \
                                                                                                                gdat.epocmtracompprio[j], gdat.pericompprio[j])
                        
                        gdat.arrypcur['primbdtrbindtotl'][b][p][j] = ephesus.rebn_tser(gdat.arrypcur['primbdtr'][b][p][j], \
                                                                                                            binsxdat=gdat.binsphasprimtotl)
                        
                        if np.isfinite(gdat.duraprio[j]):
                            gdat.arrypcur['primbdtrbindzoom'][b][p][j] = ephesus.rebn_tser(gdat.arrypcur['primbdtr'][b][p][j], \
                                                                                                            binsxdat=gdat.binsphasprimzoom[j])
                        
                        gdat.arrypcur['quadbdtr'][b][p][j] = ephesus.fold_tser(gdat.arrytser['bdtr'][b][p][gdat.listindxtimeclen[j][b][p], :], \
                                                                                                gdat.epocmtracompprio[j], gdat.pericompprio[j], phasshft=0.25)
                        
                        gdat.arrypcur['quadbdtrbindtotl'][b][p][j] = ephesus.rebn_tser(gdat.arrypcur['quadbdtr'][b][p][j], \
                                                                                                            binsxdat=gdat.binsphasquadtotl)
                        
                        path = gdat.pathdatatarg + 'arrypcurprimbdtrbind_%s_%s.csv' % (gdat.liststrgcomp[j], gdat.liststrginst[b][p])
                        if not os.path.exists(path):
                            temp = np.copy(gdat.arrypcur['primbdtrbindtotl'][b][p][j])
                            temp[:, 0] *= gdat.pericompprio[j]
                            if gdat.typeverb > 0:
                                print('Writing to %s...' % path)
                            np.savetxt(path, temp, delimiter=',', header='phase,%s,%s_err' % (gdat.liststrgtseralle[b], gdat.liststrgtseralle[b]))
                
            if gdat.boolplot:
                plot_pser(gdat, 'primbdtr')
    
    gdat.numbsamp = 1000

    #if gdat.boolplotpopl:
    #    #for strgpdfn in gdat.liststrgpdfn:
    #    if gdat.typeverb > 0:
    #        print('Making plots highlighting the %s features of the target within its population...' % (strgpdfn))
    #    plot_popl(gdat, 'prio')
    #    #calc_feat(gdat, strgpdfn)
    
    if gdat.labltarg == 'WASP-121':
        # get Vivien's GCM model
        path = gdat.pathdatatarg + 'PC-Solar-NEW-OPA-TiO-LR.dat'
        arryvivi = np.loadtxt(path, delimiter=',')
        gdat.phasvivi = (arryvivi[:, 0] / 360. + 0.75) % 1. - 0.25
        gdat.deptvivi = arryvivi[:, 4]
        indxphasvivisort = np.argsort(gdat.phasvivi)
        gdat.phasvivi = gdat.phasvivi[indxphasvivisort]
        gdat.deptvivi = gdat.deptvivi[indxphasvivisort]
        path = gdat.pathdatatarg + 'PC-Solar-NEW-OPA-TiO-LR-AllK.dat'
        arryvivi = np.loadtxt(path, delimiter=',')
        gdat.wlenvivi = arryvivi[:, 1]
        gdat.specvivi = arryvivi[:, 2]
    
        ## TESS throughput 
        gdat.data = np.loadtxt(gdat.pathdatatarg + 'band.csv', delimiter=',', skiprows=9)
        gdat.meanwlenband = gdat.data[:, 0] * 1e-3
        gdat.thptband = gdat.data[:, 1]

    if gdat.booltserdata:
        
        if gdat.typefittttvr is None:
            gdat.typefittttvr = 'globfull'

        gdat.numbsampplot = 1000
        gdat.boolbrekmodl = False

        gdat.timethisfitt = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.rflxthisfitt = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.stdvrflxthisfitt = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.varirflxthisfitt = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        gdat.timethisfittfine = [[[] for p in gdat.indxinst[b]] for b in gdat.indxdatatser]
        for b in gdat.indxdatatser:
            for p in gdat.indxinst[b]:
                if gdat.limttimefitt is None:
                    #if gdat.fitt.typemodl == 'supn':
                    #    indxtimetemp = np.argmin(abs(gdat.rflxthis[:, 0] - np.percentile(gdat.rflxthis, 1.) + \
                    #                                                            0.5 * (np.percentile(gdat.rflxthis, 99.) - np.percentile(gdat.rflxthis, 1.))))
                    #    indxtimefitt = np.where(gdat.timethis < gdat.timethis[indxtimetemp])[0]
                    #else:
                    indxtimefitt = np.arange(gdat.arrytser['bdtr'][b][p].shape[0])
                else:
                    indxtimefitt = np.where((gdat.arrytser['bdtr'][b][p][:, 0, 0] < gdat.limttimefitt[b][p][1]) & (gdat.timethis > gdat.limttimefitt[b][p][0]))[0]
                gdat.timethisfitt[b][p] = gdat.arrytser['bdtr'][b][p][indxtimefitt, 0, 0]
                gdat.rflxthisfitt[b][p] = gdat.arrytser['bdtr'][b][p][indxtimefitt, :, 1]
                gdat.stdvrflxthisfitt[b][p] = gdat.arrytser['bdtr'][b][p][indxtimefitt, :, 2]
                gdat.varirflxthisfitt[b][p] = gdat.stdvrflxthisfitt[b][p]**2
                
                minmtimethisfitt = np.amin(gdat.timethisfitt[b][p])
                maxmtimethisfitt = np.amax(gdat.timethisfitt[b][p])
                difftimethisfittfine = 0.3 * np.amin(gdat.timethisfitt[b][p][1:] - gdat.timethisfitt[b][p][:-1])
                gdat.timethisfittfine[b][p] = np.arange(minmtimethisfitt, maxmtimethisfitt + difftimethisfittfine, difftimethisfittfine)
        
        for gdat.fitt.typemodl in gdat.listtypemodl:
            
            meangauspara = None
            stdvgauspara = None

            gdat.numbsampwalk = 10
            gdat.numbsampburnwalkinit = 0
            gdat.numbsampburnwalk = int(0.3 * gdat.numbsampwalk)
            
            if gdat.fitt.typemodl.startswith('psys') or gdat.fitt.typemodl == 'cosc':
                # number of terms in the LD law
                if gdat.typemodllmdkterm == 'line':
                    gdat.numbcoeflmdkterm = 1
                if gdat.typemodllmdkterm == 'quad':
                    gdat.numbcoeflmdkterm = 2
                
                # number of distinct coefficients for each term in the LD law
                if gdat.typemodllmdkener == 'ener':
                    gdat.numbcoeflmdkener = gdat.numbener
                else:
                    gdat.numbcoeflmdkener = 1
            
            if gdat.typemodlener == 'iter':
                if gdat.typeinfe == 'samp':
                    gdat.listdictsamp = []
                else:
                    gdat.listdictmlik = []

            gdat.listnamevarbsyst = ['epocmtracomp', 'pericomp', 'cosicomp', 'rsmacomp']
            if gdat.fitt.typemodl == 'cosc':
                gdat.listnamevarbsyst += ['radistar', 'masscomp', 'massstar']
            else:
                gdat.listnamevarbsyst += ['rratcomp']
                    
            #for b in gdat.indxdatatser:
            #    for p in gdat.indxinst[b]:
                    
            if gdat.typeverb > 0:
                if gdat.fitt.typemodl == 'psys' or gdat.fitt.typemodl == 'cosc' or gdat.fitt.typemodl == 'psyspcur':
                    print('gdat.dictmileoutp[boolposianls]')
                    print(gdat.dictmileoutp['boolposianls'])
                
            # do not continue if there is no trigger
            if (gdat.fitt.typemodl == 'psys' or gdat.fitt.typemodl == 'cosc' or gdat.fitt.typemodl == 'psyspcur') and \
                                                                    gdat.boolsrchpbox and not gdat.dictmileoutp['boolposianls'].any():
                print('Skipping the forward modeling of this prior transiting object...')
                continue

            if gdat.typeverb > 0:
                print('gdat.fitt.typemodlbase')
                print(gdat.fitt.typemodlbase)
                print('gdat.typemodlener')
                print(gdat.typemodlener)
                print('gdat.numbener')
                print(gdat.numbener)
                        
            # iterate over different subsets of data
            for ee in gdat.indxdataiter:
            
                if gdat.typeinfe == 'opti':
                    path = gdat.pathdatatarg + 'paramlik.csv'
                    
                    # temp
                    if os.path.exists(path) and False:
                        print('Reading from %s...' % path)
                        objtfile = open(path, 'r')
                        gdat.liststrgeneritermlikdone = []
                        gdat.datamlik = []
                        for line in objtfile:
                            linesplt = line.split(',')
                            gdat.liststrgeneritermlikdone.append(linesplt[0]) 
                            gdat.datamlik.append(np.array(linesplt[1:]).astype(float))
                        objtfile.close()
                        gdat.liststrgeneritermlikdone = np.array(gdat.liststrgeneritermlikdone)
                    else:
                        gdat.liststrgeneritermlikdone = np.array([])

                # Boolean flag indicating whether white light curve is modeled as opposed to spectral light curves
                if ee == 0:
                    gdat.boolwhit = True
                else:
                    gdat.boolwhit = False
                
                if gdat.numbener > 1 and gdat.typemodlener == 'full':
                    gdat.indxenerthismodl = gdat.indxener[1:]
                else:
                    gdat.indxenerthismodl = np.array([ee])
                    gdat.indxdataiterthis = np.array([ee])
                
                gdat.numbenerthismodl = gdat.indxenerthismodl.size

                if gdat.typeverb > 0:
                    print('')
                    print('')
                    print('gdat.indxdataiterthis')
                    print(gdat.indxdataiterthis)
            
                if gdat.fitt.typemodl == 'supn':
                    
                    init_modl(gdat)

                    gdat.minmtimethis = np.amin(gdat.timethis)
                    gdat.maxmtimethis = np.amax(gdat.timethis)
                    
                    setp_modlbase(gdat, 'fitt', e, ee)
            
                    # define arrays of parameter indices
                    #gdat.dictindxpara[namepara] = np.empty(2, dtype=int)
                    
                    strgextn = gdat.strgcnfg + gdat.fitt.typemodl
                    proc_modl(gdat, strgextn, ee, e)
                        
                elif gdat.fitt.typemodl == 'agns':

                    init_modl(gdat)

                    setp_modlbase(gdat, 'fitt', e, ee)
            
                    proc_modl(gdat, strgextn, ee, e)


                elif gdat.fitt.typemodl == 'spot':

                    # for each spot multiplicity, fit the spot model
                    for gdat.numbspot in listindxnumbspot:
                        
                        init_modl(gdat)

                        setp_modlbase(gdat, 'fitt', e, ee)
            
                        if gdat.typeverb > 0:
                            print('gdat.numbspot')
                            print(gdat.numbspot)

                        # list of parameter labels and units
                        gdat.listlablpara = [['$u_1$', ''], ['$u_2$', ''], ['$P$', 'days'], ['$i$', 'deg'], ['$\\rho$', ''], ['$C$', '']]
                        # list of parameter scalings
                        listscalpara = ['self', 'self', 'self', 'self', 'self', 'self']
                        # list of parameter minima
                        gdat.listminmpara = [-1., -1., 0.2,   0.,  0.,-1e-1]
                        # list of parameter maxima
                        gdat.listmaxmpara = [ 3.,  3., 0.4, 89.9, 0.6, 1e-1]
                        
                        for numbspottemp in range(gdat.numbspot):
                            gdat.listlablpara += [['$\\theta_{%d}$' % numbspottemp, 'deg'], \
                                                        ['$\\phi_{%d}$' % numbspottemp, 'deg'], ['$R_{%d}$' % numbspottemp, '']]
                            listscalpara += ['self', 'self', 'self']
                            gdat.listminmpara += [-90.,   0.,  0.]
                            gdat.listmaxmpara += [ 90., 360., 0.4]
                            if gdat.boolevol:
                                gdat.listlablpara += [['$T_{s;%d}$' % numbspottemp, 'day'], ['$\\sigma_{s;%d}$' % numbspottemp, '']]
                                listscalpara += ['self', 'self']
                                gdat.listminmpara += [gdat.minmtime, 0.1]
                                gdat.listmaxmpara += [gdat.maxmtime, 20.]
                                
                        # plot light curve
                        figr, axis = plt.subplots(figsize=(8, 4))
                        # plot samples from the posterior
                        ## the sample indices which will be plotted
                        indxsampplot = np.random.choice(gdat.indxsamp, size=gdat.numbsampplot, replace=False)
                        indxsampplot = np.sort(indxsampplot)
                        listlcurmodl = np.empty((gdat.numbsampplot, gdat.numbtime))
                        listlcurmodlevol = np.empty((gdat.numbsampplot, gdat.numbspot, gdat.numbtime))
                        listlcurmodlspot = np.empty((gdat.numbsampplot, gdat.numbspot, gdat.numbtime))
                        for kk, k in enumerate(indxsampplot):
                            # calculate the model light curve for this parameter vector
                            listlcurmodl[kk, :], listlcurmodlevol[kk, :, :], listlcurmodlspot[kk, :, :] = ephesus.retr_rflxmodl(gdat, listpost[k, :])
                            axis.plot(gdat.time, listlcurmodl[kk, :], color='b', alpha=0.1)
                        
                        # plot components of each sample
                        for kk, k in enumerate(indxsampplot):
                            dictpara = pars_para(gdat, listpost[k, :])
                            plot_totl(gdat, k, listlcurmodl[kk, :], listlcurmodlevol[kk, :, :], listlcurmodlspot[kk, :, :], dictpara)

                        # plot map
                        figr, axis = plt.subplots(figsize=(8, 4))
                        gdat.numbside = 2**10
                        
                        lati = np.empty((gdat.numbsamp, gdat.numbspot))
                        lngi = np.empty((gdat.numbsamp, gdat.numbspot))
                        rrat = np.empty((gdat.numbsamp, gdat.numbspot))
                        for n in gdat.indxsamp:
                            dictpara = pars_para(gdat, listpost[n, :])
                            lati[n, :] = dictpara['lati']
                            lngi[n, :] = dictpara['lngi']
                            rrat[n, :] = dictpara['rratcomp']
                        lati = np.median(lati, 0)
                        lngi = np.median(lngi, 0)
                        rrat = np.median(rrat, 0)

                        plot_moll(gdat, lati, lngi, rrat)
                        
                        #for k in indxsampplot:
                        #    lati = listpost[k, 1+0*gdat.numbparaspot+0]
                        #    lngi = listpost[k, 1+0*gdat.numbparaspot+1]
                        #    rrat = listpost[k, 1+0*gdat.numbparaspot+2]
                        #    plot_moll(gdat, lati, lngi, rrat)

                        for sp in ['right', 'top']:
                            axis.spines[sp].set_visible(False)

                        path = gdat.pathimagtarg + 'smap%s_ns%02d.%s' % (strgtarg, gdat.numbspot, gdat.typefileplot)
                        gdat.listdictdvrp[j+1].append({'path': path, 'limt':[0., 0.05, 1., 0.1]})
                        if gdat.typeverb > 0:
                            print('Writing to %s...' % path)
                        plt.savefig(path)
                        plt.close()


                elif gdat.fitt.typemodl == 'psys' or gdat.fitt.typemodl == 'cosc' or gdat.fitt.typemodl == 'psyspcur' or gdat.fitt.typemodl == 'psysttvr':
                    
                    if gdat.fitt.typemodl == 'psysttvr':
                        if gdat.typefittttvr == 'userindi':
                            numbiterfitt = gdat.numbtran
                        elif gdat.typefittttvr == 'lineindi':
                            numbiterfitt = gdat.numbtran + 1
                        elif gdat.typefittttvr == 'glob' or gdat.typefittttvr == 'globfull':
                            numbiterfitt = 1
                    else:
                        numbiterfitt = 1
                    
                    indxiterfitt = np.arange(numbiterfitt)
                    
                    for ll in indxiterfitt:
                        
                        init_modl(gdat)

                        setp_modlbase(gdat, 'fitt', e, ee)
                        
                        strgextn = gdat.strgcnfg + gdat.fitt.typemodl
                        if gdat.typemodlener == 'iter':
                            strgextn += gdat.liststrgeneriter[gdat.indxdataiterthis[0]]
                        proc_modl(gdat, strgextn, ee, e)

                elif gdat.fitt.typemodl == 'stargpro':
                    
                    init_modl(gdat)

                    setp_modlbase(gdat, 'fitt', e, ee)
            
                    pass
                else:
                    print('A model type was not defined.')
                    print('gdat.fitt.typemodl')
                    print(gdat.fitt.typemodl)
                    raise Exception('')
            
            if gdat.typeinfe == 'samp':
                gdat.indxsampmpos = np.argmax(gdat.dictsamp['lpos'])
                gdat.numbsamp = gdat.dictsamp['lpos'].size
                gdat.indxsamp = np.arange(gdat.numbsamp)
                
                gdat.numbsampplot = min(10, gdat.numbsamp)
                gdat.indxsampplot = np.random.choice(gdat.indxsamp, gdat.numbsampplot, replace=False)

                if gdat.typeverb > 0:
                    print('gdat.numbsampplot')
                    print(gdat.numbsampplot)
            
            if gdat.numbener > 1 and (gdat.fitt.typemodl == 'psys' or gdat.fitt.typemodl == 'cosc' or gdat.fitt.typemodl == 'psyspcur'):
                # plot the radius ratio spectrum
                path = gdat.pathimagtarg + 'spec%s.%s' % (gdat.strgcnfg, gdat.typefileplot)
                figr, axis = plt.subplots(figsize=gdat.figrsizeydob)
                pmedrratcompspec = np.empty(gdat.numbener)
                perrrratcompspec = np.empty(gdat.numbener)
                for e in gdat.indxener:
                    if gdat.typeinfe == 'samp':
                        if gdat.typemodlener == 'full':
                            listrratcomp = gdat.dictsamp['rratcomp' + gdat.liststrgener[e]]
                        else:
                            listrratcomp = gdat.listdictsamp[e+1]['rratcomp' + gdat.liststrgener[e]]
                        pmedrratcompspec[e] = np.median(listrratcomp)
                        perrrratcompspec[e] = (np.percentile(listrratcomp, 86.) - np.percentile(listrratcomp, 14.)) / 2.
                    else:
                        if gdat.typemodlener == 'full':
                            pmedrratcompspec[e] = gdat.dictmlik['rratcomp' + gdat.liststrgener[e]]
                        else:
                            pmedrratcompspec[e] = gdat.listdictmlik[e+1]['rratcomp' + gdat.liststrgener[e]]
                            perrrratcompspec[e] = gdat.listdictmlik[e+1]['stdvrratcomp' + gdat.liststrgener[e]]
                axis.plot(gdat.listener, pmedrratcompspec, ls='', marker='o')
                # plot binned spectrum
                #    arry = np.zeros((dictvarbderi['rflxresi'][:, e].size, 3))
                #    arry[:, 0] = gdat.timethisfitt
                #    arry[:, 1] = dictvarbderi['rflxresi'][:, e]
                #    stdvrflxresi = np.nanstd(ephesus.rebn_tser(arry, delt=gdat.listdeltrebn[b][p])[:, 1])
                axis.plot(gdat.listener, pmedrratcompspec, ls='', marker='o')
                axis.set_ylabel('$R_p/R_*$')
                axis.set_xlabel('Wavelength [$\mu$m]')
                plt.tight_layout()
                if gdat.typeverb > 0:
                    print('Writing to %s...' % path)
                plt.savefig(path)
                plt.close()
                
                # load the spectrum to the output dictionary
                gdat.dictmileoutp['pmedrratcompspec'] = pmedrratcompspec
                gdat.dictmileoutp['perrrratcompspec'] = perrrratcompspec

                #path = gdat.pathimagtarg + 'stdvrebnener%s.%s' % (gdat.strgcnfg, gdat.typefileplot)
                #if not os.path.exists(path):
                #    figr, axis = plt.subplots(figsize=gdat.figrsizeydob)
                #    arry = np.zeros((dictvarbderi['rflxresi'][:, e].size, 3))
                #    arry[:, 0] = gdat.timethisfitt
                #    arry[:, 1] = dictvarbderi['rflxresi'][:, e]
                #    for k in gdat.indxrebn:
                #    stdvrflxresi = np.nanstd(ephesus.rebn_tser(arry, delt=gdat.listdeltrebn[b][p])[:, 1])
                #    axis.loglog(gdat.listdeltrebn[b][p], stdvrflxresi * 1e6, ls='', marker='o', ms=1, label='Binned Std. Dev')
                #    axis.axvline(gdat.ratesampener, ls='--', label='Sampling rate')
                #    axis.axvline(gdat.enerscalbdtr, ls='--', label='Detrending scale')
                #    axis.set_ylabel('RMS [ppm]')
                #    axis.set_xlabel('Bin width [$\mu$m]')
                #    axis.legend()
                #    plt.tight_layout()
                #    if gdat.typeverb > 0:
                #        print('Writing to %s...' % path)
                #    plt.savefig(path)
                #    plt.close()


    # measure final time
    gdat.timefinl = modutime.time()
    gdat.timeexec = gdat.timefinl - gdat.timeinit
    if gdat.typeverb > 0:
        print('miletos ran in %.3g seconds.' % gdat.timeexec)

    #'lygo_meannois', 'lygo_medinois', 'lygo_stdvnois', \
    for name in ['strgtarg', 'pathtarg', 'timeexec']:
        gdat.dictmileoutp[name] = getattr(gdat, name)

    path = gdat.pathdatatarg + 'dictmileoutp.pickle'
    if gdat.typeverb > 0:
        print('Writing to %s...' % path)
    
    # to be deleted
    #with open(path, 'wb') as objthand:
    #    pickle.dump(gdat.dictmileoutp, objthand)
    
    if gdat.booltserdata and gdat.boolplot and gdat.boolplotdvrp:
        listpathdvrp = []
        # make data-validation report
        for w in gdat.indxpage:
            # path of DV report
            pathplot = gdat.pathimagtarg + '%s_dvrp_pag%d.png' % (gdat.strgtarg, w + 1)
            listpathdvrp.append(pathplot)
            
            if not os.path.exists(pathplot):
                # create page with A4 size
                figr = plt.figure(figsize=(8.25, 11.75))
                
                numbplot = len(gdat.listdictdvrp[w])
                indxplot = np.arange(numbplot)
                for dictdvrp in gdat.listdictdvrp[w]:
                    axis = figr.add_axes(dictdvrp['limt'])
                    axis.imshow(plt.imread(dictdvrp['path']))
                    axis.axis('off')
                if gdat.typeverb > 0:
                    print('Writing to %s...' % pathplot)
                plt.savefig(pathplot, dpi=600)
                #plt.subplots_adjust(top=1., bottom=0, left=0, right=1)
                plt.close()
        
        gdat.dictmileoutp['listpathdvrp'] = listpathdvrp

    # write the output dictionary to target file
    path = gdat.pathdatatarg + 'mileoutp.csv'
    objtfile = open(path, 'w')
    k = 0
    for name, valu in gdat.dictmileoutp.items():
        if isinstance(valu, str) or isinstance(valu, float) or isinstance(valu, int) or isinstance(valu, bool):
            objtfile.write('%s, ' % name)
        if isinstance(valu, str):
            objtfile.write('%s' % valu)
        elif isinstance(valu, float) or isinstance(valu, int) or isinstance(valu, bool):
            objtfile.write('%g' % valu)
        if isinstance(valu, str) or isinstance(valu, float) or isinstance(valu, int) or isinstance(valu, bool):
            objtfile.write('\n')
    if typeverb > 0:
        print('Writing to %s...' % path)
    objtfile.close()
    
    # write the output dictionary to the cluster file
    if gdat.strgclus is not None:
        path = gdat.pathdataclus + 'mileoutp.csv'
        boolappe = True
        if os.path.exists(path):
            print('Reading from %s...' % path)
            dicttemp = pd.read_csv(path).to_dict(orient='list')
            if gdat.strgtarg in dicttemp['strgtarg']:
                boolappe = False
            boolmakehead = False
        else:
            print('Opening %s...' % path)
            objtfile = open(path, 'w')
            boolmakehead = True
        
        if boolappe:
            
            print('gdat.dictmileoutp')
            for name in gdat.dictmileoutp:
                if 'path' in name:
                    print(name)

            if boolmakehead:
                print('Constructing the header...')
                # if the header doesn't exist, make it
                k = 0
                listnamecols = []
                for name, valu in gdat.dictmileoutp.items():
                    
                    if name.startswith('lygo_pathsaverflx'): 
                        continue
                    
                    if name.startswith('lygo_strgtitlcntpplot'):
                        continue
                    
                    listnamecols.append(name)
                    if isinstance(valu, str) or isinstance(valu, float) or isinstance(valu, int) or isinstance(valu, bool):
                        if k > 0:
                            objtfile.write(',')
                        objtfile.write('%s' % name)
                        k += 1
                
            else:
                print('Reading from %s...' % path)
                objtfile = open(path, 'r')
                for line in objtfile:
                    listnamecols = line.split(',')
                    break
                listnamecols[-1] = listnamecols[-1][:-1]

                if not gdat.strgtarg in dicttemp['strgtarg']:
                    print('Opening %s to append...' % path)
                    objtfile = open(path, 'a')
            
            objtfile.write('\n')
            k = 0
            
            print('listnamecols')
            for name in listnamecols:
                if 'path' in name:
                    print(name)
            
            for name in listnamecols:
                valu = gdat.dictmileoutp[name]
                if isinstance(valu, str) or isinstance(valu, float) or isinstance(valu, int) or isinstance(valu, bool):
                    if k > 0:
                        objtfile.write(',')
                    if isinstance(valu, str):
                        objtfile.write('%s' % valu)
                    elif isinstance(valu, float) or isinstance(valu, int) or isinstance(valu, bool):
                        objtfile.write('%g' % valu)
                    k += 1
            #objtfile.write('\n')
            if typeverb > 0:
                print('Writing to %s...' % path)
            objtfile.close()

    return gdat.dictmileoutp


