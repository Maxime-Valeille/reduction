import glob
from astropy.io import fits
from astropy import visualization
import pylab as pl


import os
import time
import numpy as np
from astropy.io import fits
from astropy import units as u
from astropy.stats import mad_std
from astropy.table import Table
from astropy import log
import pylab as pl
import radio_beam
import glob
from spectral_cube import SpectralCube,DaskSpectralCube
from spectral_cube.lower_dimensional_structures import Projection

from casa_formats_io import Table as casaTable
#obsoleted by casaformatsio
# from casatools import image
# ia = image()

from pathlib import Path
tbldir = Path('/orange/adamginsburg/web/secure/ALMA-IMF/tables')

dataroot = '/orange/adamginsburg/ALMA_IMF/2017.1.01355.L/imaging_results'

if os.getenv('NO_PROGRESSBAR') is None and not (os.getenv('ENVIRON') == 'BATCH'):
    from dask.diagnostics import ProgressBar
    pbar = ProgressBar()
    pbar.register()

if os.environ.get('SLURM_TMPDIR'):
    os.environ['TMPDIR'] = os.environ.get("SLURM_TMPDIR")
elif not os.environ.get("TMPDIR"):
    os.environ['TMPDIR'] ='/blue/adamginsburg/adamginsburg/tmp/'
print(f"TMPDIR = {os.environ.get('TMPDIR')}")

# Dask writes some log stuff; let's make sure it gets written on local scratch
# or in a blue drive and not on orange
os.chdir(os.getenv('TMPDIR'))

threads = int(os.getenv('DASK_THREADS') or os.getenv('SLURM_NTASKS'))
print(f"Using {threads} threads.")

default_lines = {'n2hp': '93.173700GHz',
                 'sio': '217.104984GHz',
                 'h2co303': '218.222195GHz',
                 '12co': '230.538GHz',
                 'h30a': '231.900928GHz',
                 'h41a': '92.034434GHz',
                 "c18o": "219.560358GHz",
                }
lines_spw = {'n2hp': 0,
             'sio': 1,
             'h2co303': 3,
             '12co': 5,
             'h30a': 7,
             'h41a': 1,
             'c18o': 4
            }
spws = {3: list(range(4)),
        6: list(range(8)),}

suffix = '.image'

global then
then = time.time()
def dt():
    global then
    now = time.time()
    print(f"Elapsed: {now-then}")
    then = now

num_workers = None
print(f"PID = {os.getpid()}")

if __name__ == "__main__":
    if threads:
        # try dask.distrib again
        from dask.distributed import Client, LocalCluster
        import dask

        mem_mb = int(os.getenv('SLURM_MEM_PER_NODE'))
        print("Threads was set", flush=True)

        try:
            nthreads = int(threads)
            #memlimit = f'{0.8 * int(mem_mb) / int(nthreads)}MB'
            memlimit = f'{0.4*int(mem_mb)}MB'
            if nthreads > 1:
                num_workers = nthreads
                scheduler = 'threads'

            elif False:
                print(f"nthreads = {nthreads} > 1, so starting a LocalCluster with memory limit {memlimit}", flush=True)
                #scheduler = 'threads'
                # set up cluster and workers
                cluster = LocalCluster(n_workers=1,
                                       threads_per_worker=int(nthreads),
                                       memory_target_fraction=0.60,
                                       memory_spill_fraction=0.65,
                                       memory_pause_fraction=0.7,
                                       #memory_terminate_fraction=0.9,
                                       memory_limit=memlimit,
                                       silence_logs=False, # https://stackoverflow.com/questions/58014417/seeing-logs-of-dask-workers
                                      )
                print(f"Created a cluster {cluster}", flush=True)
                client = Client(cluster)
                print(f"Created a client {client}", flush=True)
                scheduler = client
                # https://github.com/dask/distributed/issues/3519
                # https://docs.dask.org/en/latest/configuration.html
                dask.config.set({"distributed.workers.memory.terminate": 0.75})
                print(f"Started dask cluster {client} with mem limit {memlimit}", flush=True)
            else:
                scheduler = 'synchronous'
        except (TypeError,ValueError) as ex:
            print(f"Exception raised when creating scheduler: {ex}", flush=True)
            nthreads = 1
            scheduler = 'synchronous'
    else:
        nthreads = 1
        scheduler = 'synchronous'

    target_chunksize = int(1e8)
    print(f"Target chunk size = {target_chunksize} (log10={np.log10(target_chunksize)})", flush=True)

    print(f"Using scheduler {scheduler} with {nthreads} threads", flush=True)
    time.sleep(1)
    print("Slept for 1s", flush=True)


    cwd = os.getcwd()
    basepath = '/orange/adamginsburg/ALMA_IMF/2017.1.01355.L/imaging_results'
    os.chdir(basepath)
    print(f"Changed from {cwd} to {basepath}, now running cube stats assembly", flush=True)

    colnames_apriori = ['Field', 'Band', 'Config', 'spw', 'line', 'suffix', 'filename', 'bmaj', 'bmin', 'bpa', 'wcs_restfreq', 'minfreq', 'maxfreq']
    colnames_fromheader = ['imsize', 'cell', 'threshold', 'niter', 'pblimit', 'pbmask', 'restfreq', 'nchan', 'width', 'start', 'chanchunks', 'deconvolver', 'weighting', 'robust', 'git_version', 'git_date', ]
    colnames_stats = 'min max std sum mean'.split() + ['mod'+x for x in 'min max std sum mean'.split()]

    colnames = colnames_apriori+colnames_fromheader+colnames_stats

    def try_qty(x):
        try:
            return u.Quantity(x)
        except:
            return list(x)

    def save_tbl(rows, colnames):
        columns = list(map(try_qty, zip(*rows)))
        tbl = Table(columns, names=colnames)
        tbl.write(tbldir / 'cube_stats.ecsv', overwrite=True)
        tbl.write(tbldir / 'cube_stats.ipac', format='ascii.ipac', overwrite=True)
        tbl.write(tbldir / 'cube_stats.html', format='ascii.html', overwrite=True)
        tbl.write(tbldir / 'cube_stats.tex', overwrite=True)
        tbl.write(tbldir / 'cube_stats.js.html', format='jsviewer')
        return tbl

    start_from_cached = True # TODO: make a parameter
    tbl = None
    if start_from_cached and os.path.exists(tbldir / 'cube_stats.ecsv'):
        tbl = Table.read(tbldir / 'cube_stats.ecsv')
        print(tbl)
        rows = [list(row) for row in tbl]
    else:
        rows = []


    cache_stats_file = open(tbldir / "cube_stats.txt", 'w')


    for field in "G010.62 W51-IRS2 G012.80 G333.60 W43-MM2 G327.29 G338.93 W51-E G353.41 G008.67 G337.92 W43-MM3 G328.25 G351.77 W43-MM1".split():
        for band in (3,6):
            for config in ('12M',): # '7M12M',
                for line in spws[band] + list(default_lines.keys()):
                    for suffix in (".image", ".contsub.image"):

                        if line not in default_lines:
                            spw = line
                            line = 'none'
                            globblob = f"{field}_B{band}_spw{spw}_{config}_spw{spw}{suffix}"
                        else:
                            globblob = f"{field}_B{band}*_{config}_*{line}{suffix}"
                            spw = lines_spw[line]


                        if tbl is not None:
                            row_matches = ((tbl['Field'] == field) &
                                           (tbl['Band'] == band) &
                                           (tbl['Config'] == config) &
                                           (tbl['line'] == line) &
                                           (tbl['spw'] == spw) &
                                           (tbl['suffix'] == suffix))
                            if any(row_matches):
                                print(f"Skipping {globblob} as complete: {tbl[row_matches]}", flush=True)
                                continue



                        fn = glob.glob(f'{dataroot}/{globblob}')

                        if any(fn):
                            print(f"Found some matches for fn {fn}, using {fn[0]}.", flush=True)
                            fn = fn[0]
                        else:
                            print(f"Found no matches for glob {globblob}", flush=True)
                            continue

                        modfn = fn.replace(".image", ".model")
                        if os.path.exists(fn) and not os.path.exists(modfn):
                            log.error(f"File {fn} is missing its model {modfn}")
                            continue

                        if line in default_lines:
                            spw = int(fn.split('spw')[1][0])

                        print(f"Beginning field {field} band {band} config {config} line {line} spw {spw} suffix {suffix}", flush=True)

                        logtable = casaTable.read(f'{fn}/logtable').as_astropy_tables()[0]
                        hist = logtable['MESSAGE']

                        #ia.open(fn)
                        #hist = ia.history(list=False)
                        history = {x.split(":")[0]:x.split(": ")[1]
                                   for x in hist if ':' in x}
                        history.update({x.split("=")[0]:x.split("=")[1].lstrip()
                                        for x in hist if '=' in x})
                        #ia.close()

                        if os.path.exists(fn+".fits"):
                            cube = SpectralCube.read(fn+".fits", format='fits', use_dask=True)
                            cube.use_dask_scheduler(scheduler=scheduler, num_workers=num_workers)
                        else:
                            cube = SpectralCube.read(fn, format='casa_image', target_chunksize=target_chunksize)
                            cube.use_dask_scheduler(scheduler=scheduler, num_workers=num_workers)
                            # print(f"Rechunking {cube} to tmp dir", flush=True)
                            # cube = cube.rechunk(save_to_tmp_dir=True)
                            # cube.use_dask_scheduler(scheduler)

                        if hasattr(cube, 'beam'):
                            beam = cube.beam
                        else:
                            beams = cube.beams
                            # use the middle-ish beam
                            beam = beams[len(beams)//2]

                        print(cube)

                        minfreq = cube.spectral_axis.min()
                        maxfreq = cube.spectral_axis.max()
                        restfreq = cube.wcs.wcs.restfrq

                        # print("getting filled data")
                        # data = cube._get_filled_data(fill=np.nan)
                        # print("finished getting filled data")
                        # del data

                        # try this as an experiment?  Maybe it's statistics that causes problems?
                        #print(f"Computing cube mean with scheduler {scheduler} and sched args {cube._scheduler_kwargs}", flush=True)
                        #mean = cube.mean()
                        print(f"Computing cube statistics with scheduler {scheduler} and sched args {cube._scheduler_kwargs}", flush=True)
                        stats = cube.statistics()
                        print("finished cube stats", flush=True)
                        min = stats['min']
                        max = stats['max']
                        std = stats['sigma']
                        sum = stats['sum']
                        mean = stats['mean']


                        #min = cube.min()
                        #max = cube.max()
                        ##mad = cube.mad_std()
                        #std = cube.std()
                        #sum = cube.sum()
                        #mean = cube.mean()

                        del cube
                        del stats

                        if os.path.exists(modfn+".fits"):
                            modcube = SpectralCube.read(modfn+".fits", format='fits', use_dask=True)
                            modcube.use_dask_scheduler(scheduler=scheduler, num_workers=num_workers)
                        else:
                            modcube = SpectralCube.read(modfn, format='casa_image', target_chunksize=target_chunksize)
                            modcube.use_dask_scheduler(scheduler=scheduler, num_workers=num_workers)
                            # print(f"Rechunking {modcube} to tmp dir", flush=True)
                            # modcube = modcube.rechunk(save_to_tmp_dir=True)
                            # modcube.use_dask_scheduler(scheduler)

                        print(modcube, flush=True)
                        print(f"Computing model cube statistics with scheduler {scheduler} and sched args {modcube._scheduler_kwargs}", flush=True)
                        modstats = modcube.statistics()
                        modmin = modstats['min']
                        modmax = modstats['max']
                        modstd = modstats['sigma']
                        modsum = modstats['sum']
                        modmean = modstats['mean']

                        del modcube
                        del modstats

                        row = ([field, band, config, spw, line, suffix, fn, beam.major.value, beam.minor.value, beam.pa.value, restfreq, minfreq, maxfreq] +
                            [history[key] if key in history else '' for key in colnames_fromheader] +
                            [min, max, std, sum, mean] +
                            [modmin, modmax, modstd, modsum, modmean])
                        rows.append(row)

                        cache_stats_file.write(" ".join(map(str, row)) + "\n")
                        cache_stats_file.flush()
                        tbl = save_tbl(rows, colnames)

    cache_stats_file.close()


    print(tbl)

    os.chdir(cwd)

    if threads and nthreads > 1 and 'client' in locals():
        client.close()
