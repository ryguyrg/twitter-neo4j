"""
This file is responsible to manage buckets
"""

'''
Built-in modules
'''
import pdb
import os
import uuid

'''
User defined modules
'''
from libs.twitter_logging import console_logger as logger

store_type = os.getenv("DB_STORE_TYPE", "file_store")
if store_type.lower() == "file_store":
    from libs.file_store import DMFileStoreIntf as DMStoreIntf
else:
    from libs.cypher_store import DMCypherStoreIntf as DMStoreIntf

from libs.dmcheck_client_manager import DMCheckClientManager

'''
Constants
'''
DMCHECK_DEFAULT_BUCKET_SIZE = 180
DMCHECK_BUCKET_DEFAULT_PRIORITY = 100


class utils:
    @staticmethod
    def chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

class DMCheckBucketManager:

    def __init__(self):
        self.dataStoreIntf = DMStoreIntf()
        self.dmcheck_client_manager = DMCheckClientManager()

    #TODO: provide capability to specify max number of buckets count
    def add_buckets(self):
        buckets= self.__get_buckets()
        
        if len(buckets):
            db_buckets = self.__make_db_buckets(buckets)
            self.dataStoreIntf.add_dmcheck_buckets(db_buckets)
            pass
        else:
            logger.info("No users found")
        return

    def assignBuckets(self, client_id, bucketscount=1):
        logger.info("Assigning {} bucket(s) to the client".format(bucketscount, client_id))
        if not self.dmcheck_client_manager.client_registered(client_id):
            logger.error("Unregistered client {} is trying to get buckets".format(client_id))
            return None
        buckets = self.dataStoreIntf.assign_dmcheck_buckets(client_id, bucketscount)
        logger.debug("Assigned {} bucket(s) to the client".format(buckets))
        buckets_for_client = []
        for id in buckets:
            users = self.dataStoreIntf.get_all_users_for_bucket(id)
            buckets_for_client.append({'bucket_id':id, 'users':users})
        return buckets_for_client
    
    def __release_bucket(self, bucket_id):
        #Assumption: It assumes that bucket exists
        print("Releasing [{}] bucket".format(bucket_id))
        users = self.dataStoreIntf.get_all_users_for_bucket(bucket_id)
        if len(users):
            logger.warn("{}Bucket still has {} unprocessed users".format(bucket_id, len(users)))
            self.dataStoreIntf.empty_dmcheck_bucket(bucket_id)
        self.dataStoreIntf.remove_bucket(bucket_id)
        print("Successfully released [{}] bucket".format(bucket_id))

    def __store_dmcheck_status_for_bucket(self, client_id, bucket_id, users):
        candm_users = [user for user in users if user['candm'].upper()=="DM"]
        cantdm_users = [user for user in users if user['candm'].upper()=="NON_DM"]
        unknown_users = [user for user in users if user['candm'].upper()=="UNKNOWN"]
        #TODO: Try to make atomic for each bucket
        self.dataStoreIntf.store_dm_friends(client_id, bucket_id, candm_users)
        self.dataStoreIntf.store_nondm_friends(client_id, bucket_id, cantdm_users)
        self.dataStoreIntf.store_dmcheck_unknown_friends(client_id, bucket_id, unknown_users)
        
    def storeDMCheckInfoForBucket(self, client_id, bucket):
        logger.info("Got {} bucket from the client".format(len(bucket['bucket_id']), client_id))
        if not self.dmcheck_client_manager.client_registered(client_id):
            logger.error("Unregistered client {} is trying to update DM Check for buckets".format(client_id))
            return
        bucket_id = bucket['bucket_id']
        print("Processing bucket with ID [{}]".format(bucket_id))
        if not  self.dataStoreIntf.valid_bucket_owner(bucket_id, client_id):
            logger.error("[{}] client is trying to update DM Check for [{}] bucket not owned by itself".format(bucket_id, client_id))
            return
        #TODO: Sanity check user info
        users = bucket['users']
        self.__store_dmcheck_status_for_bucket(client_id, bucket_id, users)
        self.__release_bucket(bucket_id)
        print("Successfully processed {} bucket".format(bucket['bucket_id']))
        return       

    def __make_db_buckets(self, buckets, priority=DMCHECK_BUCKET_DEFAULT_PRIORITY):
        db_buckets = []
        for bucket in buckets:
            db_bucket=[{'name': user} for user in bucket]
            uuid = uuid.uuid4().hex
            print("Generated {} UUID for bucket".format(uuid))
            db_buckets.append({'bucket_uuid':uuid, 'bucket_priority': priority, 'bucket_state':"unassigned", 'bucket':db_bucket})
        return db_buckets

    def __get_buckets(self, bucketsize = DMCHECK_DEFAULT_BUCKET_SIZE):
        logger.info("Making buckets with {} size".format(bucketsize))
        #TODO: make single call for getting list as current code is not optimized
        users = self.dataStoreIntf.get_all_nonprocessed_list()
        bucket_users = self.dataStoreIntf.get_all_users_in_dmchech_buckets()
        users_wkg = sorted(set(users) - set(bucket_users))
        buckets = list(utils.chunks(users_wkg, bucketsize))
        logger.info("Got {} buckets".format(len(buckets)))
        return buckets
