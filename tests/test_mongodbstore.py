## -*- coding: utf-8 -*-
"""Test the MongoDB Store

This filed copied entirely from the python-openid storetest.py.
Copyright JanRain
Apache Software License

"""
from unittest import TestCase
import string, time, random
from openid.cryptutil import randomString
from openid.association import Association
from openid.store.nonce import mkNonce, split

allowed_handle = []
for c in string.printable:
    if c not in string.whitespace:
        allowed_handle.append(c)
allowed_handle = ''.join(allowed_handle)

def generateHandle(n):
    return randomString(n, allowed_handle)

generateSecret = randomString

def _store_check(store):
    """Make sure a given store has a minimum of API compliance. Call
    this function with an empty store.

    Raises AssertionError if the store does not work as expected.

    OpenIDStore -> NoneType
    """
    ### Association functions
    now = int(time.time())

    server_url = 'http://www.myopenid.com/openid'

    horrid_server_url = 'http://\xd0\x98asdf\xd0\xbaw\xd1\x89\xd0\xbe/opnid'
    bad_server_url = 'http:www.openid.com/'
    def genAssoc(issued, lifetime=600):
        sec = generateSecret(20)
        hdl = generateHandle(128)
        return Association(hdl, sec, now + issued, lifetime, 'HMAC-SHA1')

    def checkRetrieve(url, handle=None, expected=None):
        retrieved_assoc = store.getAssociation(url, handle)
        assert retrieved_assoc == expected, (retrieved_assoc, expected)
        if expected is not None:
            if retrieved_assoc is expected:
                print ('Unexpected: retrieved a reference to the expected '
                       'value instead of a new object')
            assert retrieved_assoc.handle == expected.handle
            assert retrieved_assoc.secret == expected.secret

    def checkRemove(url, handle, expected):
        present = store.removeAssociation(url, handle)
        assert bool(expected) == bool(present)

    assoc = genAssoc(issued=0)

    # Make sure that a missing association returns no result
    checkRetrieve(server_url)

    # Check that after storage, getting returns the same result
    store.storeAssociation(server_url, assoc)
    checkRetrieve(server_url, None, assoc)

    # Check that after storage, getting returns the same result for a nasty url
    store.storeAssociation(horrid_server_url, assoc)
    checkRetrieve(horrid_server_url, None, assoc)

    # Check that storing a bad url doesn't work
    try:
        store.storeAssociation(bad_server_url, assoc)
    except ValueError, e:
        pass
    else:
        assert False, "expected ValueError for server_url %s" % bad_server_url

    # more than once
    checkRetrieve(server_url, None, assoc)

    # Storing more than once has no ill effect
    store.storeAssociation(server_url, assoc)
    checkRetrieve(server_url, None, assoc)

    # Removing an association that does not exist returns not present
    checkRemove(server_url, assoc.handle + 'x', False)

    # Removing an association that does not exist returns not present
    checkRemove(server_url + 'x', assoc.handle, False)

    # Removing an association that is present returns present
    checkRemove(server_url, assoc.handle, True)

    # but not present on subsequent calls
    checkRemove(server_url, assoc.handle, False)

    # Put assoc back in the store
    store.storeAssociation(server_url, assoc)

    # More recent and expires after assoc
    assoc2 = genAssoc(issued=1)
    store.storeAssociation(server_url, assoc2)

    # After storing an association with a different handle, but the
    # same server_url, the handle with the later issue date is returned.
    checkRetrieve(server_url, None, assoc2)

    # We can still retrieve the older association
    checkRetrieve(server_url, assoc.handle, assoc)

    # Plus we can retrieve the association with the later issue date
    # explicitly
    checkRetrieve(server_url, assoc2.handle, assoc2)

    # More recent, and expires earlier than assoc2 or assoc. Make sure
    # that we're picking the one with the latest issued date and not
    # taking into account the expiration.
    assoc3 = genAssoc(issued=2, lifetime=100)
    store.storeAssociation(server_url, assoc3)

    checkRetrieve(server_url, None, assoc3)
    checkRetrieve(server_url, assoc.handle, assoc)
    checkRetrieve(server_url, assoc2.handle, assoc2)
    checkRetrieve(server_url, assoc3.handle, assoc3)

    checkRemove(server_url, assoc2.handle, True)

    checkRetrieve(server_url, None, assoc3)
    checkRetrieve(server_url, assoc.handle, assoc)
    checkRetrieve(server_url, assoc2.handle, None)
    checkRetrieve(server_url, assoc3.handle, assoc3)

    checkRemove(server_url, assoc2.handle, False)
    checkRemove(server_url, assoc3.handle, True)

    checkRetrieve(server_url, None, assoc)
    checkRetrieve(server_url, assoc.handle, assoc)
    checkRetrieve(server_url, assoc2.handle, None)
    checkRetrieve(server_url, assoc3.handle, None)

    checkRemove(server_url, assoc2.handle, False)
    checkRemove(server_url, assoc.handle, True)
    checkRemove(server_url, assoc3.handle, False)

    checkRetrieve(server_url, None, None)
    checkRetrieve(server_url, assoc.handle, None)
    checkRetrieve(server_url, assoc2.handle, None)
    checkRetrieve(server_url, assoc3.handle, None)

    checkRemove(server_url, assoc2.handle, False)
    checkRemove(server_url, assoc.handle, False)
    checkRemove(server_url, assoc3.handle, False)

    ### test expired associations
    # assoc 1: server 1, valid
    # assoc 2: server 1, expired
    # assoc 3: server 2, expired
    # assoc 4: server 3, valid
    assocValid1 = genAssoc(issued=-3600,lifetime=7200)
    assocValid2 = genAssoc(issued=-5)
    assocExpired1 = genAssoc(issued=-7200,lifetime=3600)
    assocExpired2 = genAssoc(issued=-7200,lifetime=3600)

    store.cleanupAssociations()
    store.storeAssociation(server_url + '1', assocValid1)
    store.storeAssociation(server_url + '1', assocExpired1)
    store.storeAssociation(server_url + '2', assocExpired2)
    store.storeAssociation(server_url + '3', assocValid2)

    cleaned = store.cleanupAssociations()
    assert cleaned == 2, cleaned

    ### Nonce functions

    def checkUseNonce(nonce, expected, server_url, msg=''):
        stamp, salt = split(nonce)
        actual = store.useNonce(server_url, stamp, salt)
        assert bool(actual) == bool(expected), "%r != %r: %s" % (actual, expected,
                                                                 msg)

    for url in [server_url, '']:
        # Random nonce (not in store)
        nonce1 = mkNonce()

        # A nonce is allowed by default
        checkUseNonce(nonce1, True, url)

        # Storing once causes useNonce to return True the first, and only
        # the first, time it is called after the store.
        checkUseNonce(nonce1, False, url)
        checkUseNonce(nonce1, False, url)

        # Nonces from when the universe was an hour old should not pass these days.
        old_nonce = mkNonce(3600)
        checkUseNonce(old_nonce, False, url, "Old nonce (%r) passed." % (old_nonce,))


    old_nonce1 = mkNonce(now - 20000)
    old_nonce2 = mkNonce(now - 10000)
    recent_nonce = mkNonce(now - 600)

    from openid.store import nonce as nonceModule
    orig_skew = nonceModule.SKEW
    try:
        nonceModule.SKEW = 0
        store.cleanupNonces()
        # Set SKEW high so stores will keep our nonces.
        nonceModule.SKEW = 100000
        assert store.useNonce(server_url, *split(old_nonce1))
        assert store.useNonce(server_url, *split(old_nonce2))
        assert store.useNonce(server_url, *split(recent_nonce))

        nonceModule.SKEW = 3600
        cleaned = store.cleanupNonces()
        assert cleaned == 2, "Cleaned %r nonces." % (cleaned,)

        nonceModule.SKEW = 100000
        # A roundabout method of checking that the old nonces were cleaned is
        # to see if we're allowed to add them again.
        assert store.useNonce(server_url, *split(old_nonce1))
        assert store.useNonce(server_url, *split(old_nonce2))
        # The recent nonce wasn't cleaned, so it should still fail.
        assert not store.useNonce(server_url, *split(recent_nonce))
    finally:
        nonceModule.SKEW = orig_skew

class TestMongoDBStore(TestCase):

    def setUp(self):
        from openidmongodb import MongoDBStore
        self.store = MongoDBStore(db="openid_test")

    def test_mongodbstore(self):
        _store_check(self.store)

    def tearDown(self):
        self.store._conn.drop_database('openid_test')
