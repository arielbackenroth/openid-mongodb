"""MongoDB Store

This back-end is heavily based on the RedisStore from the openid-redis package.
"""
import time, logging
from openid.store import nonce
from openid.store.interface import OpenIDStore
from openid.association import Association
from pymongo import Connection
from pymongo.errors import DuplicateKeyError

log = logging.getLogger(__name__)

__all__ = ["MongoDBStore"]

class MongoDBStore(OpenIDStore):

    def __init__(self, host="localhost", port=27017, db="openid",
                 associations_collection="associations", nonces_collection="nonces"):
        self._conn = Connection(host, int(port))
        self.associations = self._conn[db][associations_collection]
        self.nonces = self._conn[db][nonces_collection]
        self.log_debug = logging.DEBUG >= log.getEffectiveLevel()
        super(MongoDBStore, self).__init__()

    def storeAssociation(self, server_url, association):
        if self.log_debug:
            log.debug("Storing association for server_url: %s, with handle: %s",
                      server_url, association.handle)
        if server_url.find('://') == -1:
            raise ValueError('Bad server URL: %r' % server_url)
        self.associations.insert({
            "_id": hash((server_url, association.handle)),
            "server_url": server_url,
            "handle": association.handle,
            "association": association.serialize(),
            "expires": time.time() + association.expiresIn
        })

    def getAssociation(self, server_url, handle=None):
        if self.log_debug:
            log.debug("Association requested for server_url: %s, with handle: %s",
                      server_url, handle)
        if server_url.find('://') == -1:
            raise ValueError('Bad server URL: %r' % server_url)
        if handle is None:
            associations = self.associations.find({
                "server_url": server_url
            })
            if associations.count():
                associations = [Association.deserialize(a['association'])
                                for a in associations]
                # Now use the one that was issued most recently
                associations.sort(cmp=lambda x, y: cmp(x.issued, y.issued))
                log.debug("Most recent is %s", associations[-1].handle)
                return associations[-1]
        else:
            association = self.associations.find_one({
                "_id": hash((server_url, handle)),
                "server_url": server_url,
                "handle": handle
            })
            if association:
                return Association.deserialize(association['association'])

    def removeAssociation(self, server_url, handle):
        if self.log_debug:
            log.debug('Removing association for server_url: %s, with handle: %s',
                      server_url, handle)
        if server_url.find('://') == -1:
            raise ValueError('Bad server URL: %r' % server_url)
        res = self.associations.remove({"_id": hash((server_url, handle)),
                                        "server_url": server_url,
                                        "handle": handle},
                                       safe=True)
        return bool(res['n'])

    def cleanupAssociations(self):
        r = self.associations.remove(
            {"expires": {"$gt": time.time()}},
            safe=True)
        return r['n']

    def useNonce(self, server_url, timestamp, salt):
        if abs(timestamp - time.time()) > nonce.SKEW:
            if self.log_debug:
                log.debug('Timestamp from current time is less than skew')
            return False

        n = hash((server_url, timestamp, salt))
        try:
            self.nonces.insert({"_id": n,
                                "server_url": server_url,
                                "timestamp": timestamp,
                                "salt": salt},
                               safe=True)
        except DuplicateKeyError, e:
            if self.log_debug:
                log.debug('Nonce already exists: %s', n)
            return False
        else:
            return True

    def cleanupNonces(self):
        r = self.nonces.remove(
            {"$or": [{"timestamp": {"$gt": time.time() + nonce.SKEW}},
                     {"timestamp": {"$lt": time.time() - nonce.SKEW}}]},
            safe=True)
        return r['n']
