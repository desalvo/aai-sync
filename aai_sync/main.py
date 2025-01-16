import argparse
import configparser
import ldap
import os
import sys


def sync():
    config = configparser.ConfigParser()
    config.read('%s/.aai-sync.conf' % os.environ['HOME'])
    default_binddn = config['secrets']['BINDDN']
    default_bindpw = config['secrets']['BINDPW']

    site_branch = 'roma1'
    local_branch = 't2rm1'
    default_search_base = 'ou=People,dc=infn,dc=it'
    default_site_search_base = f'ou=People,dc={site_branch},dc=infn,dc=it'
    default_local_search_base = f'ou=People,dc={local_branch},dc=infn,dc=it'
    default_filter = "atlas"
    filters = {
                'atlas' : '(isMemberOf=s:csn1:atlas::*)',
                'cms'   : '(isMemberOf=s:csn1:cms::*)',
                'cygno' : '(isMemberOf=s:csn2:cygno::*)',
                'sicr'  : '(i:infn:roma1:servizio_calcolo_e_reti::n:member)'
              }
    parser = argparse.ArgumentParser(
                    prog='aai-sync',
                    description='Synchronize AAI entries into the local branch',
                    epilog='Alessandro De Salvo <Alessandro.DeSalvo@roma1.infn.it>')
    parser.add_argument('-b', '--base-search', nargs=1, default=[default_search_base], help='LDAP base search (default "%s")' % default_search_base)
    parser.add_argument('-s', '--site-base-search', nargs=1, default=[default_site_search_base], help='LDAP site base search (default "%s")' % default_site_search_base)
    parser.add_argument('-l', '--local-base-search', nargs=1, default=[default_local_search_base], help='LDAP base search (default "%s")' % default_local_search_base)
    parser.add_argument('-f', '--filter', nargs=1, help='LDAP search filter (default "%s")' % filters[default_filter])
    parser.add_argument('-a', '--attribute', action='append', help='LDAP search attribute')
    parser.add_argument('-H', '--host', nargs=1, default=['ds.roma1.infn.it'], help='LDAP host')
    parser.add_argument('--binddn', nargs=1, default=[default_binddn], help='LDAP binddn')
    parser.add_argument('-g', '--group', nargs=1, default=['atlas'], help='Group of users')
    parser.add_argument('--bindpw', nargs=1, default=[default_bindpw], type=ascii, help='LDAP bindpw')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug output')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()


    ldap_host = 'ldap://%s' % args.host[0]
    searchScope = ldap.SCOPE_SUBTREE
    baseSearches = [args.base_search[0],args.site_base_search[0],args.local_base_search[0]]
    if (args.filter): searchFilter = args.filter[0]
    elif (args.group): searchFilter = filters[args.group[0]]
    else: searchFilter = filters[default_filter]
    if (args.attribute): searchAttributes = args.attribute
    else: searchAttributes = ['infnuuid','infnlinkeduuid','infnKerberosPrincipal','mail','mailalternateaddress','uid','uidnumber','gidnumber','givenName','sn','cn']

    ds = ldap.initialize(ldap_host)
    try:
        binddn = args.binddn[0]
        bindpw = args.bindpw[0]
        ds.protocol_version = ldap.VERSION3
        ds.simple_bind(binddn, bindpw)
    except ldap.INVALID_CREDENTIALS:
        print ("Invalid credentials of user '%s'" % args.binddn[0])
        sys.exit(1)
    except ldap.SERVER_DOWN:
        print ("The server %s is down" % ldap_host)
        sys.exit(2)
    except Exception as e:
        print (f"ERROR: {e=}, {type(e)=}")
        sys.exit(2)

    result_sets = []
    for baseSearch in baseSearches:
        if (args.debug):
            print ("\n-----> %s <------\n" % baseSearch)
            print ("\n-----> %s <------\n" % searchFilter)
            print ("\n-----> %s <------\n" % searchAttributes)
        try:
            ldap_results = ds.search(baseSearch, searchScope, searchFilter, searchAttributes)
            result_set = []
            while 1:
                result_type, result_data = ds.result(ldap_results, 0)
                if (result_data == []):
                    break
                else:
                    if result_type == ldap.RES_SEARCH_ENTRY:
                        if ('uid' in result_data[0][1].keys()):
                            result_set.append(result_data)
                        else:
                            print (f"No uid in record {result_data[0][1].keys()}")
                            sys.exit(10)
            if (args.debug):
                for res in result_set:
                    print (f">>> {res}")
                    for entry in res:
                        print (f"{entry[0]}")
                        for attr in entry[1].keys():
                            print (f"  - {attr}: {entry[1][attr][0].decode('utf-8')}")
            result_sets.append(result_set)
        except ldap.FILTER_ERROR as e:
            print (f"ERROR: {e=}, {type(e)=}")
            print (f"FILTER: {searchFilter}")
            sys.exit(3)
        except Exception as e:
            print (f"ERROR: {e=}, {type(e)=}")
            sys.exit(3)

    ds.unbind()

    # Find people matching in the top branch but not present in the local branch
    add_user = []
    user_count = [0,0]
    for top_entry in result_sets[0]:
        for top_uid in top_entry:
            found = 0
            for local_entry in result_sets[2]:
                for local_uid in local_entry:
                    if (top_uid[1]['infnuuid'] == local_uid[1]['infnlinkeduuid']):
                        found = 1
                        if (args.verbose): print (f"Skipping user {local_uid[1]['uid'][0].decode('utf-8')}")
                        break
            user_count[0] += 1
            if (found == 0):
                add_user.append(top_uid)
                user_count[1] += 1
    if (args.verbose):
        print (f"Total users: {user_count[0]}")
        print (f"New users: {user_count[1]}")
    for user in add_user:
        uid = user[1]['uid'][0].decode('utf-8')
        infnlinkeduuid = user[1]['infnlinkeduuid'][0].decode('utf-8')
        givenName = user[1]['givenName'][0].decode('utf-8')
        sn = user[1]['sn'][0].decode('utf-8')
        if ('infnKerberosPrincipal' in user[1].keys()):
            infnKerberosPrincipal = user[1]['infnKerberosPrincipal'][0].decode('utf-8')
        else:
            infnKerberosPrincipal = ""
        mail = user[1]['mail'][0].decode('utf-8')
        if ('mailalternateaddress' in user[1].keys()):
            mailalternateaddress = user[1]['mailalternateaddress'][0].decode('utf-8')
        else:
            mailalternateaddress = ""
        print (f"ssh -p 57847 extuserserv@protoserv.infn.it ADD \"{local_branch}:{uid}:{infnlinkeduuid}:{givenName}:{sn}:{infnKerberosPrincipal}:{mail}:{mailalternateaddress}\"")
