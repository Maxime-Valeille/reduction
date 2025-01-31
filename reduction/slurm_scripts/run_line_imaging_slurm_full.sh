# Image whole bands
if [ $CMD ]; then
    echo $CMD
else
    CMD=/orange/adamginsburg/ALMA_IMF/reduction/reduction/slurm_scripts/run_line_imaging_slurm.sh
fi
export FIELD_ID=$1
if [[ $2 ]]; then
    export BAND_TO_IMAGE=$2
    export BAND_NUMBERS=${BAND_TO_IMAGE/B/}
    echo "Imaging only band $BAND_TO_IMAGE"
else
    export BAND_NUMBERS=3
    export BAND_TO_IMAGE=B${BAND_NUMBERS}
fi

if [[ $3 ]]; then
    export SPW_TO_IMAGE=$3
    echo "Imaging only spw $SPW_TO_IMAGE"
fi

if [[ $BAND_TO_IMAGE == "B3" ]]; then
    export MEM=64gb
    export MEM=128gb

    if [[ $CMD == *"mpi"* ]]; then
        export NTASKS=32
        export CPUS_PER_TASK=1 # mem/4
        export SLURM_TASKS_PER_NODE=$NTASKS
    else
        export NTASKS=1
        export CPUS_PER_TASK=32 # mem/4
    fi
    export SLURM_NTASKS=$NTASKS


    export LOGPATH=/blue/adamginsburg/adamginsburg/slurmjobs/

    if [ -z $QOS ]; then
        export QOS=adamginsburg-b
    fi

    case $QOS in
        *adamginsburg*)
            export ACCOUNT=adamginsburg
            ;;
        *astronomy-dept*)
            export ACCOUNT=astronomy-dept
            ;;
    esac

    if [ $CONTINUE_IF_MS_EXISTS ]; then
        echo "Continue if ms exists: ${CONTINUE_IF_MS_EXISTS}"
    else
        # default: let's allow for the existence of the MS file
        # (this can happen if the cleaning times out)
        export CONTINUE_IF_MS_EXISTS=True
    fi


    # re-trying without specifying giant memory - chanchunks should be able to handle this, right?
    # WRONG! Chanchunks doesn't help because automultithresh is a poop.
    case $FIELD_ID in
    #G338.93|W51-E|W51-IRS2|G10.62) # B3 needs bigger; B6 is probably OK w/96
    #    declare -A mem_map=( ["0"]="64gb" ["3"]="64gb" ["6"]="64gb" ["7"]="64gb" ) ;;
    W43-MM2|W51-IRS2|G333.60|W51-E) #B3 B6
    #    export MEM=96gb ;;
        export MEM=256gb ;;
    #G333.60|W43-MM3|G353.41|G351.77|G337.92) #B3 B6
    #    export MEM=96gb ;;
    #W43-MM1|W43-MM2|G008.67) # only B3 needs more...
    #    export MEM=96gb ;;
    #esac
    #case $FIELD_ID in
    #G338.93|W51-E|W51-IRS2|G10.62) # B3 needs bigger; B6 is probably OK w/96
    #    export CHANCHUNKS=64 ;;
    #G333.60|W43-MM3|G353.41|G351.77|G337.92) #B3 B6
    #    export CHANCHUNKS=32 ;;
    #W43-MM1|W43-MM2|G008.67) # only B3 needs more...
    #    export CHANCHUNKS=16 ;;
    esac

    if [ -z $EXCLUDE_7M ]; then
        export EXCLUDE_7M=True
        suffix12m="12M"
    else
        if [ $EXCLUDE_7M == "True" ]; then
            suffix12m="12M"
        else
            suffix12m="7M12M"
        fi
    fi

    if [ -z $DO_CONTSUB ]; then
        suffix_contsub=""
    else
        if [ $DO_CONTSUB == "True" ]; then
            suffix_contsub="_cs"
        else
            suffix_contsub=""
        fi
    fi

    echo field=$FIELD_ID band=$BAND_TO_IMAGE mem=$MEM exclude_7m=$EXCLUDE_7M suffix=${suffix12m} contsub=${suffix_contsub} nodeps=${NODEPS} QOS=${QOS}

    if [ $EXCLUDE_7M == "False" ]; then
        if [ $suffix12m != "7M12M" ]; then
            exit 1;
        fi
    fi

    jobid=""
    for SPW in {0..3}; do

        if [[ $SPW_TO_IMAGE && ! $SPW_TO_IMAGE == $SPW ]]; then
            continue
        fi

        export LINE_NAME=spw${SPW}

        jobname=${FIELD_ID}_${BAND_TO_IMAGE}_fullcube_${suffix12m}_${SPW}${suffix_contsub} 

        export LOGFILENAME="${LOGPATH}/casa_log_line_${jobname}_$(date +%Y-%m-%d_%H_%M_%S).log"

        if [ ${jobid##* } ]; then
            if [ -z $NODEPS ]; then
                dependency="--dependency=afterok:${jobid##* }"
            else
                dependency=""
            fi
        else
            dependency=""
        fi

        # use sacct to check for jobname
        job_running=$(sacct --format="JobID,JobName%45,Account%15,QOS%17,State,Priority%8,ReqMem%8,CPUTime%15,Elapsed%15,Timelimit%15,NodeList%20" | grep RUNNING | grep $jobname)

        if [[ $job_running ]]; then
            echo "Skipped job $jobname because it's running"
        else
            jobid=$(sbatch --ntasks=${NTASKS} --cpus-per-task=${CPUS_PER_TASK} --mem=${MEM} --output=${jobname}_%j.log --job-name=${jobname} --account=${ACCOUNT} --qos=${QOS} --export=ALL ${dependency} $CMD)
            echo ${jobid##* }
        fi
        #export EXCLUDE_7M=False
        #export LOGFILENAME="${LOGPATH}/casa_log_line_${FIELD_ID}_${BAND_TO_IMAGE}_${SPW}_fullcube_7M${suffix12m}_$(date +%Y-%m-%d_%H_%M_%S).log"
        #jobid=$(sbatch --dependency=afterok:${jobid##* } --output=${FIELD_ID}_${BAND_TO_IMAGE}_fullcube_7M${suffix12m}_${SPW}_%j.log --job-name=${FIELD_ID}_${BAND_TO_IMAGE}_fullcube_7M12M_${SPW} --export=ALL $CMD)
        #echo ${jobid##* }
    done
fi

if [[ ! $2 ]]; then
    export BAND_NUMBERS=6
    export BAND_TO_IMAGE=B${BAND_NUMBERS}
fi

if [[ $BAND_TO_IMAGE == "B6" ]]; then
    jobid=""

    export MEM=32gb
    export MEM=128gb

    if [[ $CMD == *"mpi"* ]]; then
        export NTASKS=32
        export CPUS_PER_TASK=1 # mem/4
        export SLURM_TASKS_PER_NODE=$NTASKS
    else
        export NTASKS=1
        export CPUS_PER_TASK=32 # mem/4
    fi
    export SLURM_NTASKS=$NTASKS

    case $FIELD_ID in
    W51-IRS2|G10.62|G333.60|W51-E|W43-MM3|G353.41|G351.77|G338.93|G337.92|G328.25)
        declare -A mem_map=( ["0"]="128gb" ["1"]="128gb" ["3"]="128gb" ["6"]="128gb" ["7"]="128gb" ) ;;
    esac

    echo field=$FIELD_ID band=$BAND_TO_IMAGE mem=$MEM exclude_7m=$EXCLUDE_7M suffix=${suffix12m} contsub=${suffix_contsub}

    for SPW in {0..7}; do
        if [[ $SPW_TO_IMAGE && ! $SPW_TO_IMAGE == $SPW ]]; then
            continue
        fi

        export LINE_NAME=spw${SPW}

        if [ ${jobid##* } ]; then
            if [ -z $NODEPS ]; then
                dependency="--dependency=afterok:${jobid##* }"
            else
                dependency=""
            fi
        else
            dependency=""
        fi

        # ternary operator - if `mem_map` doesn't exist, or if `mem_map[$blah]` doesn't exist, will set back to default
        [[ ${mem_map[$SPW]} ]] && export MEM=${mem_map[$SPW]} || export MEM=128gb

        jobname=${FIELD_ID}_${BAND_TO_IMAGE}_fullcube_${suffix12m}_${SPW}${suffix_contsub}
        export LOGFILENAME="${LOGPATH}/casa_log_line_${jobname}_$(date +%Y-%m-%d_%H_%M_%S).log"


        # use sacct to check for jobname
        job_running=$(sacct --format="JobID,JobName%45,Account%15,QOS%17,State,Priority%8,ReqMem%8,CPUTime%15,Elapsed%15,Timelimit%15,NodeList%20" | grep RUNNING | grep $jobname)

        if [[ $job_running ]]; then
            echo "Skipped job $jobname because it's running"
        else
            jobid=$(sbatch --ntasks=${NTASKS} --cpus-per-task=${CPUS_PER_TASK} --mem=${MEM} --output=${jobname}_%j.log --job-name=$jobname --account=${ACCOUNT} --qos=${QOS} --export=ALL ${dependency} $CMD)
            echo ${jobid##* }
        fi
        #export EXCLUDE_7M=False
        #export LOGFILENAME="${LOGPATH}/casa_log_line_${FIELD_ID}_${BAND_TO_IMAGE}_${SPW}_fullcube_7M${suffix12m}_$(date +%Y-%m-%d_%H_%M_%S).log"
        #jobid=$(sbatch --dependency=afterok:${jobid##* } --output=${FIELD_ID}_${BAND_TO_IMAGE}_${SPW}_fullcube_7M${suffix12m}_%j.log --job-name=${FIELD_ID}_${BAND_TO_IMAGE}_fullcube_7M12M_${SPW} --export=ALL $CMD)
        #echo ${jobid##* }
    done
fi
