#!/usr/bin/env python2
# requester.py
# ---------------
# Author: Zhongheng Li
# Init Date: 10-01-2018
# Updated Date: 10-08-2018

"""



"""


from __future__ import print_function
from airflow.operators.bash_operator import BashOperator
from airflow.models import DAG
from datetime import datetime

args = {
    'owner': 'airflow',
    'start_date': datetime.now(),
}

dag = DAG(
    dag_id='Batch_image_submission_simulation', default_args=args,
    schedule_interval=None)


def print_context(i):
    print(i)
    return 'print_context has sucess {}'.format(i)


templated_command_1 = """


split -l 160 ~/all_labels.txt sample_labels_

peg scp to-rem pySpark-cluster 1 ~/sample_labelsaa /home/ubuntu/sample_labels_aa

peg scp to-rem pySpark-cluster 2 ~/sample_labelsab /home/ubuntu/sample_labels_ab

peg scp to-rem pySpark-cluster 3 ~/sample_labelsac /home/ubuntu/sample_labels_ac

peg scp to-rem pySpark-cluster 4 ~/sample_labelsad /home/ubuntu/sample_labels_ad

"""


Labels_files_prep = \
    BashOperator(
        task_id='Data_file_prep',
        bash_command=templated_command_1,
        dag=dag)



templated_command_2 = """

peg sshcmd-node pySpark-cluster 1 "nohup sh ~/Deep_Images_Hub/src/producer/auto_upload.sh ~/sample_labelsaa "validation"  > ~/Deep_Images_Hub/src/producer/auto_upload.log &" 

peg sshcmd-node pySpark-cluster 2 "nohup sh ~/Deep_Images_Hub/src/producer/auto_upload.sh ~/sample_labelsab "validation"  > ~/Deep_Images_Hub/src/producer/auto_upload.log &" 

peg sshcmd-node pySpark-cluster 3 "nohup sh ~/Deep_Images_Hub/src/producer/auto_upload.sh ~/sample_labelsac "validation"  > ~/Deep_Images_Hub/src/producer/auto_upload.log &" 

peg sshcmd-node pySpark-cluster 4 "nohup sh ~/Deep_Images_Hub/src/producer/auto_upload.sh ~/sample_labelsad "validation"  > ~/Deep_Images_Hub/src/producer/auto_upload.log &" 



"""




Batch_image_submissions = \
    BashOperator(
        task_id='batch_image_submissions',
        bash_command=templated_command_2,
        dag=dag)



Labels_files_prep >> Batch_image_submissions



