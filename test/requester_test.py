#!/usr/bin/env python2
# requester_test.py
# ---------------
# Author: Zhongheng Li
# Init Date: 10-01-2018
# Updated Date: 10-02-2018

"""

requester is used by end users to make request on image classicfication models with their choices of classes.

 Temp: ...
 TODO: ...

 Given: user_id, classes_list, destination_bucket

 1. Get user_info from user_id
 2. Verify classes
    1. Check the images counts for each given label is there enough images for training - Threshold: 500
 3. If there are enough images:
        1. Train the model with given labels of images
            1. Bring up the Training Cluster with EMR with specified AMI
                1. Lambda Function when ready trigger train
                2. When training is done, send the zip and send the model to CPU node to create the CoreML model
                    1. Start Tiering Down the GPU cluster
                3. When CoreML model is created, send both the TF trained model, Training Plot and CoreML model to the user's bucket
                4. Once completed tier down the last CPU node.
                5. Notify user by e-mail the model is ready with Lambda funciton

            2. Train the model
            3. Send the model back to
        2. Convert the model with to CoreML model
        3. Send both the weights and CoreML model to user's bucket
        4. Notify user when ready.
    If there is not enough images for training:
        1. Store the shorted labels into a list
        2. Send user an e-mail to notify him that there is not enough trainig data for the listing labels at the moment.
 **4. Use is able to subscribe to a label of images Subscribe to a



    Run with .....:

    example:
        requester.py "s3://insight-deep-images-hub/users/username_organization_id/models/packaged_food"

        python requester.py --des_bucket_name "insight-deep-images-hub" --des_prefix "user/userid/model/" --label_List 'Apple' 'Banana' 'protein_bar'  --user_id 2


"""

from __future__ import print_function
import sys
from argparse import ArgumentParser
from configparser import ConfigParser
import os
import boto3
from io import BytesIO
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import psycopg2
from psycopg2 import extras
from geopy.geocoders import Nominatim
import json
import time
import datetime
import random
import math
import numpy as np
from os.path import dirname as up


import pandas as pd


"""
Commonly Shared Statics

"""

# Set up project path
projectPath = up(up(os.getcwd()))

s3_bucket_name = "s3://insight-data-images/"

database_ini_file_path = "/utilities/database/database.ini"





"""

config Database

"""

def config(filename=projectPath+database_ini_file_path, section='postgresql'):
    # create a parser
    parser = ConfigParser()
    # read config file
    parser.read(filename)

    # get section, default to postgresql
    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return db




# Invoke model training script to train model in TensorflowOnSpark with the requesting labels
def invoke_model_training(label_list,user_info):

    #TODO
    print("Invoking model training process...")
    print("Training started")




if __name__ == '__main__':

    # Set up argument parser
    parser = ArgumentParser()
    parser.add_argument("-des_b", "--des_bucket_name", help="Destination S3 bucket name", required=True)
    parser.add_argument("-des_p", "--des_prefix", help="Destination S3 folder prefix", required=True)
    parser.add_argument("-l", "--label_List", nargs='+', help="images label", required=True)
    parser.add_argument("-uid", "--user_id", help="requester user id", required=True)

    args = parser.parse_args()

    # Assign input, output files and number of lines variables from command line arguments
    des_bucket_name = args.des_bucket_name
    prefix = args.des_prefix
    label_list = args.label_List
    user_id = args.user_id


    user_info = { "destination_bucket" : des_bucket_name,
                   "destination_prefix" : prefix,
                   "user_id"    : user_id


    }


    # # verify_labels(label_list)
    # # verify_labels_quantities(label_list,user_info)
    #
    #
    # image_urls_df = get_images_urls(label_list)
    #
    # filePath = image_urls_df.image_url[0]
    #
    #
    # # strip off the starting s3a:// from the bucket
    # bucket = os.path.dirname(str(filePath))[6:].split("/", 1)[0]
    # key = os.path.basename(str(filePath))
    # path  = filePath[6:].split("/", 1)[1:][0]
    #
    #
    # print(bucket)
    # print(key)
    # print(path)






"""

For Testing

"""




def get_images_urls(label_list):


    label_nums = list(range(len(label_list)))


    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

        results_list = []

        for i, label_name in enumerate(label_list):

            sql = "SELECT full_hadoop_path FROM images WHERE label_name =  %s ;"

            cur.execute(sql,(label_name,))

            results = [r[0] for r in cur.fetchall()]

            print(results)

            results_list.append(results)

        # close the communication with the PostgreSQL
        cur.close()

        # All labels ready return True
        return results_list

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')



"""
For testing purpose

"""

import PIL.Image
import keras
from keras.applications.imagenet_utils import preprocess_input
from keras_preprocessing import image

def load_image_from_uri(local_uri):


  # img = (PIL.Image.open(local_uri).convert('RGB').resize((299, 299), PIL.Image.ANTIALIAS))
  img = (get_image_array_from_S3_file(local_uri))

  img_arr = np.array(img).astype(np.float32)
  img_tnsr = preprocess_input(img_arr[np.newaxis, :])
  return img_tnsr



# this function will use boto3 on the workers directly to pull the image
# and then decode it, all in this function
def get_image_array_from_S3_file(image_url):
    import boto3
    import os

    # TODO - will need to implement exceptions handling

    s3 = boto3.resource('s3')

    # strip off the starting s3a:// from the bucket
    bucket_name = os.path.dirname(str(image_url))[6:].split("/", 1)[0]
    key = image_url[6:].split("/", 1)[1:][0]

    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(key)
    img = image.load_img(BytesIO(obj.get()['Body'].read()), target_size=(299, 299))

    return img


    # if contents:
    #     try:
    #
    #         img = image.load_img(contents, target_size=(299, 299))
    #
    #         plt.figure(0)
    #         plt.imshow(img)
    #         plt.title('Sample Image from S3')
    #         plt.pause(0.05)
    #
    #         return img
    #     except:
    #         return None



labels_urls_list = get_images_urls(label_list)


image_url = labels_urls_list[0][0]

print(image_url)

img = get_image_array_from_S3_file(image_url)


plt.figure(0)
plt.imshow(img)
plt.title('Sample Image from S3')
plt.pause(0.05)


img_tnsr = load_image_from_uri(image_url)
print (img_tnsr)

# for label in labels_urls_list:
#     for url in label:
#         img_tnsr = load_image_from_uri(url)
#         print(type(img_tnsr))