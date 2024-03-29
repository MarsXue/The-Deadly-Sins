import cloudant
from cloudant.client import CouchDB
import time
from typing import *
import random
import requests
import const

import config

class DBHelper:
    def __init__(self) -> None:
        self.client = CouchDB(config.couchdb_user, config.couchdb_auth_token, \
            url=config.couchdb_host, admin_party=config.couchdb_admin_party, connect=True, use_basic_auth=True)
        self.node_id = config.node_id

                            
    def get_process_job(self) -> Optional[Tuple[str, str]]:
        r = requests.get(config.couchdb_host + "/go_backend/message_queue/get_preprocess_job", {"token": config.couchdb_auth_token})
        if r.status_code == 200:
            j = r.json()
            return (j["dbType"], j["jobID"])
        if r.status_code == 404:
            # no more job
            return None
        raise Exception("Unable to get a job", r.status_code, r.text)



    def lock_process_job(self, db_name: str, id: str) -> cloudant.document:
        # try to lock this job
        doc = self.client[db_name][id]
        # ignore local cache
        doc.fetch()

        deadline = int(time.time()) - const.PROCESS_JOB_TIMEOUT
        if doc["process_meta"]["lock_timestamp"] > deadline or doc["process_meta"]["processed"] == True:
            print("=============")
            print(doc["_id"])
            print(doc["process_meta"]["lock_timestamp"])
            print(doc["process_meta"]["processed"])
            raise Exception("job have been taken.")

        doc["process_meta"]["lock_timestamp"] = int(time.time())
        doc["process_meta"]["work_node"] = config.node_id
        doc.save()

        return doc
    
    def mark_as_finished(self, doc: cloudant.document) -> None:
        doc["process_meta"]["processed"] = True
        doc.save()


    def submit_result(self, db_name: str, job_doc: cloudant.document, data: Dict[str, Any]) -> None:
        process_meta = {
            'source': db_name,
            'finished_time': int(time.time()),
            'work_node': config.node_id
        }
        result_doc = {
            '_id': job_doc["_id"],
            'data': data,
            'process_meta': process_meta
        }
        self.client["tweet_data"].create_document(result_doc, False)

    def get_tweet_image_with_yolo(self, url: str) -> Optional[Any]:
        if url in self.client["tweet_image_with_yolo"]:
            doc = self.client["tweet_image_with_yolo"][url]

            return {
                "url": doc["_id"],
                "yolo": doc["yolo"]
            }
        else:
            return None


    def add_tweet_image_with_yolo(self, url: str, yolo: Any, file_content: Any, tweet_id: str) -> None:
        doc = {
            '_id': url,
            'yolo': yolo,
            'work_node': config.node_id,
            'time': int(time.time()),
            'tweet_id': tweet_id
        }
        doc = self.client["tweet_image_with_yolo"].create_document(doc, True)
        doc.put_attachment("small.jpg", "image/jpeg", file_content)
