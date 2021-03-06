# -*- coding: utf-8 -*-
# !/usr/bin/env python2
# producer_local.py
# ---------------
# Author: Zhongheng Li
# Init Date: 09-18-2018
# Updated Date: 10-14-2018

"""

Producer is used to process incoming images that are sending as a batch from the user.
The producer will perform the following tasks to process the images:

 Temp: Take images from S3 bucket instead of getting image from user's phone
 TODO: Accept images from user submissions from iOS devices



    Run with .:

    example:
            time python ~/Deep_Images_Hub/src/producer/producer_local.py --src_bucket_name "insight-data-images" --src_prefix "dataset/not_occluded/"  --src_type "test" --des_bucket_name "insight-deep-images-hub"  --label_name "Coconut" --lon -73.935242 --lat 40.730610 --user_id 1

"""
from __future__ import print_function

from argparse import ArgumentParser
from configparser import ConfigParser
import boto3
from io import BytesIO
import psycopg2
from psycopg2 import extras
from geopy.geocoders import Nominatim
import datetime
import random
from os.path import dirname as up

import logging
import os
import io

import PIL
from PIL import Image




"""
Commonly Shared Statics

"""

# Set up project path
projectPath = os.getcwd()

database_ini_file_path = "/Deep_Images_Hub/utilities/database/database.ini"


# Following set up are referenced from https://realpython.com/python-logging/
# Create a custom logger
logger = logging.getLogger(__name__)

# Create handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler('producer_local.log')
c_handler.setLevel(logging.INFO)
f_handler.setLevel(logging.ERROR)

# Create formatters and add it to handlers
c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)





"""

config Database

"""


def config(filename=projectPath + database_ini_file_path, section='postgresql'):
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


"""
Create Batch ID to keep track of this submission once the images are uploaded into Deep Image Hub

"""


def generate_new_batch_id(user_id, place_id, image_counter):
    sql = "INSERT INTO images_batches (user_id, ready, place_id, submitted_count, on_board_date ) VALUES %s RETURNING batch_id;"

    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        logger.info('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

        values_list = []

        values = (
            user_id,
            False,
            place_id,
            image_counter,
            datetime.datetime.now()
        )

        values_list.append(values)

        # writing image info into the database
        # execute a statement
        logger.info('writing image batch info into the database...')
        psycopg2.extras.execute_values(cur, sql, values_list)
        # commit the changes to the database
        conn.commit()

        batch_id = cur.fetchone()[0]
        # close the communication with the PostgreSQL
        cur.close()

        return batch_id
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)
    finally:
        if conn is not None:
            conn.close()
            logger.info('Database connection closed.')


"""
Analysing Image Label

"""


def verify_label(label_name):
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        logger.info('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

        sql = "SELECT count(label_name)  FROM labels WHERE label_name = %s ;"

        # verify if label exist in the database

        # execute a statement
        logger.info('Verifying if the label existed in the database...')
        cur.execute(sql, (label_name,))

        result_count = cur.fetchone()[0]

        if result_count == 1:
            logger.info("Label existed")
            return True
        else:
            logger.error("Label doesn't exist")
            return False

        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)
    finally:
        if conn is not None:
            conn.close()
            logger.info('Database connection closed.')


# Recursively getting the parents' labels using Common Table Expressions(CTEs)
def getParent_labels(label_name):
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        logger.info('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

        sql ="""
          
            WITH RECURSIVE labeltree AS (
                SELECT parent_name 
                FROM labels 
                  WHERE label_name = %s 
                  UNION ALL 
                  SELECT l.parent_name 
                  FROM labels l 
                  INNER JOIN labeltree ltree ON ltree.parent_name = l.label_name 
                      WHERE l.parent_name IS NOT NULL 
                ) 
                SELECT * 
                FROM labeltree;
        
        """


        # recursively split out the parent's label one by one to construct the path for the bucket's prefix
        # execute a statement
        logger.info('Recursively getting the labels\' parents...')
        cur.execute(sql, (label_name,))

        row = cur.fetchone()

        parent_labels = []

        while row is not None:
            parent_labels.insert(0, row[0])
            row = cur.fetchone()

        return parent_labels

        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)
    finally:
        if conn is not None:
            conn.close()
            logger.info('Database connection closed.')


# Construct the path for the bucket's prefix
def construct_bucket_prefix(parent_labels):
    prefix = ""

    for label in parent_labels:
        prefix = prefix + "/" + label

    return prefix


"""
Analysing geoinfo

"""


"""
Generating geoinfo

    # Raw Location Data Sample:
    # {'place_id': '138622978', 'licence': 'Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright',
    #  'osm_type': 'way', 'osm_id': '265159179', 'lat': '40.7364439', 'lon': '-73.9339868252163',
    #  'display_name': '51-27, 35th Street, Blissville, Queens County, NYC, New York, 11101, USA',
    #  'address': {'house_number': '51-27', 'road': '35th Street', 'neighbourhood': 'Blissville',
    #              'county': 'Queens County', 'city': 'NYC', 'state': 'New York', 'postcode': '11101', 'country': 'USA',
    #              'country_code': 'us'}, 'boundingbox': ['40.7362729', '40.7365456', '-73.9340831', '-73.9338454']}

"""


def generate_random_geo_point(lon, lat):
    dec_lat = random.random() / 20
    dec_lon = random.random() / 20

    new_lon = lon + dec_lon
    new_lat = lat + dec_lat

    return new_lon, new_lat


def getGeoinfo(lon, lat):
    geolocator = Nominatim(user_agent="specify_your_app_name_here")
    lat_lon_str = str(lat) + ", " + str(lon)

    location = geolocator.reverse(lat_lon_str)

    try:
        location.raw['address']['neighbourhood']
        return location.raw['place_id'], location.raw['licence'], location.raw['address']['postcode'], \
               location.raw['address']['neighbourhood'], location.raw['address']['city'], location.raw['address'][
                   'country']

    except KeyError as e:
        logger.warning("Can not find this address from Nominatim")
        return 1, "UNKNOWN", 0, "UNKNOWN", "UNKNOWN", "UNKNOWN"


def writeGeoinfo_into_DB(image_info):
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        logger.info('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

        sql = "INSERT \
                       INTO \
                       places(place_id, licence, postcode, neighbourhood, city, country, lon, lat, geometry, time_added) VALUES \
                       (" + str(image_info['place_id']) + ", '" + image_info['geo_licence'] + \
              "', " + str(image_info['postcode']) + \
              ", '" + image_info['neighbourhood'] + "', '" + image_info['city'] + \
              "', '" + image_info['country'] + "', " + str(image_info['lon']) + \
              ", " + str(image_info['lat']) + ", '" + str(image_info['geo_point']) + "', (SELECT NOW()) ) \
                       ON CONFLICT(place_id)\
                       DO NOTHING RETURNING place_id;"

        # Insert geoinfo into database if place_id is not already exist

        # execute a statement
        logger.info('Inserting geoinfo into database if place_id is not already exist...')

        # print(values)

        cur.execute(sql)

        # commit the changes to the database
        conn.commit()

        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)
    finally:
        if conn is not None:
            conn.close()
            logger.info('Database connection closed.')


"""
Fetch images, *compare image embeddings and put image to the proper folder in the AWS bucket

"""

def import_images_from_source(bucket, prefix, destination_prefix, image_info):
    for obj in bucket.objects.filter(Prefix=prefix).all():



        if '.jpg' in obj.key:


            # Create thumbnail images for web and model training
            img = Image.open(BytesIO(obj.get()['Body'].read()))
            img = img.resize((299, 299), PIL.Image.ANTIALIAS)

            in_mem_file = io.BytesIO()
            img.save(in_mem_file, format="JPEG")

            # Create the smaller thumbnail images for web
            img_small = img.resize((100, 100), PIL.Image.ANTIALIAS)
            in_mem_file_small = io.BytesIO()
            img_small.save(in_mem_file_small, format="JPEG")


            # Temp - Copy the the file from source bucket to destination bucket
            old_source = {'Bucket': 'insight-data-images',
                          'Key': obj.key}

            new_key = obj.key.replace(prefix,
                                      "data/images" + destination_prefix + "/" + image_info['final_label_name'] + "/")

            filename = new_key.split('/')[-1].split('.')[0]

            logger.info("Put file in to: ", new_key)
            logger.info("filename: ", filename)

            new_obj = new_bucket.Object(new_key)
            new_obj.copy(old_source)

            global new_keys
            new_keys.append(new_key)

            # Create thumbnails for Web

            new_thumbnail_key = obj.key.replace(prefix,
                                                "data/images/thumbnail" + destination_prefix + "/" + image_info[
                                                    'final_label_name'] + "/")

            new_small_thumbnail_key = obj.key.replace(prefix,
                                                "data/images/thumbnail_small" + destination_prefix + "/" + image_info[
                                                    'final_label_name'] + "/")

            thumbnail_path = "https://s3.amazonaws.com/insight-deep-images-hub/" + new_thumbnail_key

            samll_thumbnail_path = "https://s3.amazonaws.com/insight-deep-images-hub/" + new_small_thumbnail_key

            global new_thumbnail_keys
            new_thumbnail_keys.append(thumbnail_path)

            global new_small_thumbnail_keys
            new_small_thumbnail_keys.append(samll_thumbnail_path)


            # Put thumbnails to S3
            s3 = boto3.client('s3')
            s3.put_object(Body=in_mem_file.getvalue(), Bucket=des_bucket_name, Key=new_thumbnail_key,
                          ContentType='image/jpeg', ACL='public-read')

            s3.put_object(Body=in_mem_file_small.getvalue(), Bucket=des_bucket_name, Key=new_small_thumbnail_key,
                          ContentType='image/jpeg', ACL='public-read')

            # increase image_counter by 1
            global image_counter
            image_counter += 1



"""
Save metadata in DB

"""

def write_imageinfo_to_DB(obj_keys, thumbnail_keys,small_thumbnail_keys, image_info):
    sql_images_insert = """ INSERT INTO \
     images(image_object_key,image_thumbnail_object_key,image_thumbnail_small_object_key, bucket_name, full_hadoop_path, parent_labels, label_name, batch_id, submission_time, user_id, place_id, image_index, embeddings, verified)\
     VALUES %s
     """

    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        logger.info('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

        # update label's count TODO - No need to update count at the moment Update when verified
        logger.info('Updating the image counts for the label: ', image_info['final_label_name'])

        sql_update_counts_on_label = """
        
    
        UPDATE labels 
        SET image_count = image_count + %s 
        WHERE label_name = %s ; 
        
    
        
        """

        values = (

            str(image_info['image_counter']),
            image_info['final_label_name']

            ,)

        cur.execute(sql_update_counts_on_label, values)

        # writing image info into the database
        # execute a statement
        logger.info('writing images info into the database...')

        # create values list
        values_list = []

        # hadoop s3a prefix
        s3a_prefix = 's3a://'

        for i, obj_key in enumerate(obj_keys):
            values = (obj_key,
                      thumbnail_keys[i],
                      small_thumbnail_keys[i],
                      image_info['destination_bucket'],
                      s3a_prefix + image_info['destination_bucket'] + '/' + obj_key,
                      image_info['destination_prefix'],
                      image_info['final_label_name'],
                      image_info['batch_id'],
                      datetime.datetime.now(),
                      image_info['user_id'],
                      image_info['place_id'],
                      None,
                      # images_features[i].astype(float).tolist(),
                      None,
                      True  # TODO -- For now with out batch filtering
                      )

            values_list.append(values)

        psycopg2.extras.execute_values(cur, sql_images_insert, values_list)
        # commit the changes to the database
        conn.commit()

        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)
    finally:
        if conn is not None:
            conn.close()
            logger.info('Database connection closed.')


if __name__ == '__main__':

    # Set up argument parser
    parser = ArgumentParser()
    parser.add_argument("-src_b", "--src_bucket_name", help="Source S3 bucket name", required=True)
    parser.add_argument("-src_p", "--src_prefix", help="Source S3 folder prefix", required=True)
    parser.add_argument("-src_t", "--src_type",
                        help="From train, test or validation folder *Not needed for production for phone submission")
    parser.add_argument("-des_b", "--des_bucket_name", help="Destination S3 bucket name", required=True)
    parser.add_argument("-l", "--label_name", help="images label", required=True)
    parser.add_argument("-lon", "--lon", help="longitude", required=True)
    parser.add_argument("-lat", "--lat", help="latitude", required=True)
    parser.add_argument("-uid", "--user_id", help="supplier user id", required=True)

    args = parser.parse_args()

    # Assign input, output files and number of lines variables from command line arguments
    src_bucket_name = args.src_bucket_name
    des_bucket_name = args.des_bucket_name

    src_type = args.src_type

    label_name = args.label_name
    lon = float(args.lon)
    lat = float(args.lat)
    user_id = args.user_id
    prefix = args.src_prefix + src_type + '/' + label_name + '/'

    # Set up geo points with geojson
    geo_point = (lon, lat)

    # From
    s3 = boto3.resource('s3', region_name='us-east-1')
    bucket = s3.Bucket(src_bucket_name)

    # To
    destination_prefix = ""
    new_bucket = s3.Bucket(des_bucket_name)

    # Variables
    final_label_name = ""
    parent_labels = []

    # Verifying Label if exist
    isLabel = verify_label(label_name)

    if isLabel == False:
        print("Sorry the supplying label doesn't exist in database")
        exit()

    final_label_name = label_name
    logger.info("final_label_name: ", final_label_name)

    # Setting up the path for the prefix to save the images to the S3 bucket
    parent_labels = getParent_labels(label_name)
    destination_prefix = construct_bucket_prefix(parent_labels)

    # Analyzing geo info
    lon, lat = generate_random_geo_point(lon, lat)

    place_id, geo_licence, postcode, neighbourhood, city, country = getGeoinfo(lon, lat)

    image_info = {"destination_bucket": des_bucket_name,
                  "destination_prefix": destination_prefix,
                  "final_label_name": final_label_name,
                  "user_id": user_id,
                  "place_id": place_id,
                  "geo_licence": geo_licence,
                  "postcode": postcode,
                  "neighbourhood": neighbourhood,
                  "city": city,
                  "country": country,
                  "geo_point": geo_point,
                  "lon": lon,
                  "lat": lat

                  }

    # Insert geoinfo into database if place_id is not already exist
    writeGeoinfo_into_DB(image_info)

    # Initiate an empty list of new object keys (as string) of where the image object locate at destinated S3 bucket
    new_keys = []

    # Initiate an empty list of new thumbnail keys (as string) of where the image object locate at destinated S3 bucket
    new_thumbnail_keys = []

    # Initiate an empty list of new small thumbnail keys (as string) of where the image object locate at destinated S3 bucket
    new_small_thumbnail_keys = []

    # Initiate an empty list of numpy array representation the images
    images_in_numpy_arrays = []

    # Initiate image_counter
    image_counter = 0

    # Processing images
    import_images_from_source(bucket, prefix, destination_prefix, image_info)

    logger.info("Added " + str(image_counter) + " images.")
    image_info['image_counter'] = image_counter


    batch_id = generate_new_batch_id(user_id, place_id, image_counter)

    logger.info("batch_id:", batch_id)

    image_info['batch_id'] = batch_id

    # Bulk upload image info to database
    # write_imageinfo_to_DB(new_keys,images_features[0], image_info)
    write_imageinfo_to_DB(new_keys, new_thumbnail_keys, new_small_thumbnail_keys, image_info)
