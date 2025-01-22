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
    default_site_search_base = 'ou=People,dc=%s,dc=infn,dc=it'
    default_local_search_base = 'ou=People,dc=%s,dc=infn,dc=it'
    default_local_search_group = 'ou=group,dc=%s,dc=infn,dc=it'
    default_local_filter_group = '(cn=%s)'
    default_group = 'atlas'
    defaultHomeDir = 'atlas'
    defaultGidNumber = 'roma1'
    homeDirs = { 'atlas': '/atlashome/%s', 'cms': '/cmshome/%s', 'cygno': '/cygnohome/%s', 'sicr': '/atlashome/%s' }
    defaultShell = '/bin/bash'
    preferredKerberosRealm = "INFN.IT"
    localUidAllowedRange = [12000,18000]
    groups = { 'atlas': 1307, 'cms': 1399, 'cygno': 31022, 'roma1': 30006, 'sicr': 31001 }
    localSearchBase = default_local_search_base % local_branch
    siteSearchBase = default_site_search_base % site_branch
    localGroupSearch = default_local_search_group % local_branch
    localGroupFilter =  default_local_filter_group % default_group
    localGroupSearchAttributes = ['cn','memberUid']

    filters = {
                'atlas' : '(isMemberOf=i:infn:*:csn1:atlas*)',
                'cms'   : '(isMemberOf=i:infn:*:csn1:cms*)',
                'cygno' : '(isMemberOf=i:infn:*:csn2:cygno*)',
                'sicr'  : '(isMemberOf=i:infn:roma1:servizio_calcolo_e_reti::n:member)'
              }
    baseGroupSearch = f'ou=group,dc={local_branch},dc=infn,dc=it'

    parser = argparse.ArgumentParser(
                    prog='aai-sync',
                    description='Synchronize AAI entries into the local branch',
                    epilog='Alessandro De Salvo <Alessandro.DeSalvo@roma1.infn.it>')
    parser.add_argument('-b', '--base-search', nargs=1, default=[default_search_base], help='LDAP base search (default "%s")' % default_search_base)
    parser.add_argument('--binddn', nargs=1, default=[default_binddn], help='LDAP binddn')
    parser.add_argument('--bindpw', nargs=1, default=[default_bindpw], type=ascii, help='LDAP bindpw')
    parser.add_argument('-a', '--attribute', action='append', help='LDAP search attribute')
    parser.add_argument('--local-branch', nargs=1, default=[local_branch], help='LDAP local branch name (default "%s")' % local_branch)
    parser.add_argument('--site-branch', nargs=1, default=[site_branch], help='LDAP site branch name (default "%s")' % site_branch)
    parser.add_argument('-d', '--debug', action='store_true', help='Debug output')
    parser.add_argument('-D', '--home-dir', nargs=1, help='Home dir pattern')
    parser.add_argument('-f', '--filter', nargs=1, help='LDAP search filter (default "%s")' % filters[default_group])
    parser.add_argument('-F', '--force', action='store_true', help='Force processing')
    parser.add_argument('-g', '--group', nargs=1, default=['atlas'], help='Group of users')
    parser.add_argument('-G', '--gid', nargs=1, default=[groups[defaultGidNumber]], help='Gid number (default "%s")' % groups[defaultGidNumber])
    parser.add_argument('--local-group-search', nargs=1, default=None, help='LDAP local group search (default "%s")' % localGroupSearch)
    parser.add_argument('--local-group-filter', nargs=1, default=None, help='LDAP local group filter (default "%s")' % localGroupFilter)
    parser.add_argument('-H', '--host', nargs=1, default=['ds-t2.roma1.infn.it'], help='LDAP host')
    parser.add_argument('-l', '--local-base-search', nargs=1, default=None, help='LDAP base search (default "%s")' % localSearchBase)
    parser.add_argument('-L', '--site-to-local', action='store_true', help='Add only users from site to local')
    parser.add_argument('-o', '--output', nargs=1, help='File output destination')
    parser.add_argument('-r', '--kerberos-realm', nargs=1, default=[preferredKerberosRealm], help='Preferred Kerberos Realm (default "%s")' % preferredKerberosRealm)
    parser.add_argument('-s', '--site-base-search', nargs=1, default=None, help='LDAP site base search (default "%s")' % siteSearchBase)
    parser.add_argument('-S', '--shell', nargs=1, default=[defaultShell], help='Default shell for POSIX data')
    parser.add_argument('-u', '--uid', nargs=1, help='Filter only this uid')
    parser.add_argument('--uid-file', nargs=1, help='Filter only this uid reading the list from file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()


    ldap_host = 'ldap://%s' % args.host[0]
    searchScope = ldap.SCOPE_SUBTREE
    if (args.filter): searchFilter = args.filter[0]
    elif (args.group):
        if (args.group[0] in filters.keys()):
            searchFilter = filters[args.group[0]]
        else:
            print ("Group must be one of the following:")
            for group in filters.keys(): print (f"  - {group}")
            sys.exit(10)
    else: searchFilter = filters[default_group]
    if (args.uid): searchFilter = f"(&(uid={args.uid[0]}){searchFilter})"
    if (args.uid_file):
        if (os.path.exists(args.uid_file[0])):
            uidFile = open(args.uid_file[0],"r")
            uidFilter = "|"
            for uid in uidFile:
                value = uid.rstrip('\n')
                uidFilter += f"(uid={value})"
            uidFile.close()
            if (uidFilter != "|"): searchFilter = f"(&({uidFilter}){searchFilter})"
        else:
            print (f"File path not found: {args.uid_file[0]}")
            sys.exit(5)
    if (args.local_base_search):  localBaseSearch = args.local_base_search[0]
    else:                         localBaseSearch = default_local_search_base % args.local_branch[0]
    if (args.site_base_search):   siteBaseSearch = args.site_base_search[0]
    else:                         siteBaseSearch = default_site_search_base % args.site_branch[0]
    if (args.local_group_search): localGroupSearch = args.local_group_search[0]
    else:                         localGroupSearch = default_local_search_group % args.local_branch[0]
    if (args.local_group_filter): localGroupFilter = args.local_group_filter[0]
    else:                         localGroupFilter = default_local_filter_group % args.group[0]
    if (args.site_to_local):
        baseSearches = [siteBaseSearch,siteBaseSearch,localBaseSearch]
        searchFilters = [searchFilter,searchFilter,"(uid=*)"]
    else:
        baseSearches = [args.base_search[0],siteBaseSearch,localBaseSearch]
        searchFilters = [searchFilter,searchFilter,"(uid=*)"]
    if (args.home_dir): homeDir = args.home_dir[0]
    elif (args.group):
        if (args.group[0] in homeDirs.keys()):
            homeDir = homeDirs[args.group[0]]
    else: homeDir = homeDirs[defaultHomeDir]
    if (args.attribute): searchAttributes = args.attribute
    else: searchAttributes = ['infnuuid','infnlinkeduuid','infnKerberosPrincipal','mail','mailalternateaddress','uid','uidnumber','gidnumber','givenName','sn','cn']

    ds = ldap.initialize(ldap_host)
    try:
        binddn = args.binddn[0]
        bindpw = args.bindpw[0]
        ds.protocol_version = ldap.VERSION3
        ds.simple_bind_s(binddn, bindpw)
    except ldap.INVALID_CREDENTIALS:
        print ("Invalid credentials of user '%s'" % args.binddn[0])
        sys.exit(1)
    except ldap.SERVER_DOWN:
        print ("The server %s is down" % ldap_host)
        sys.exit(2)
    except Exception as e:
        print (f"ERROR: {e=}, {type(e)=}")
        sys.exit(2)

    # Build the group list
    localGroupList = []
    localGroups = {}
    if (args.debug):
        print ()
        print ("-----> %s <------" % localGroupSearch)
        print ("-----> %s <------" % localGroupFilter)
        print ("-----> %s <------\n" % localGroupSearchAttributes)
    try:
        ldap_results = ds.search(localGroupSearch, searchScope, localGroupFilter, localGroupSearchAttributes)
        while 1:
            result_type, result_data = ds.result(ldap_results, 0)
            if (result_data == []):
                break
            else:
                if result_type == ldap.RES_SEARCH_ENTRY:
                    localGroupList.append(result_data)
        for group in localGroupList:
            for entry in group:
                groupName = entry[1]['cn'][0].decode('utf-8')
                if (args.debug): print (f">>> GROUP NAME: {groupName}")
                if (groupName not in localGroups.keys()): localGroups[groupName] = []
                if ('memberUid' in entry[1].keys()):
                    for member in entry[1]['memberUid']:
                        memberUid = member.decode('utf-8')
                        if (args.debug): print (f"  - {memberUid}")
                        localGroups[groupName].append(memberUid)
    except ldap.FILTER_ERROR as e:
        print (f"ERROR: {e=}, {type(e)=}")
        print (f"FILTER: {localGroupFilter}")
        sys.exit(3)
    except Exception as e:
        print (f"ERROR: {e=}, {type(e)=}")
        sys.exit(3)

    # Build the user list
    result_sets = {}
    baseSearchIndex = 0
    for baseSearch in baseSearches:
        baseSearchIndex += 1
        if (baseSearch not in result_sets.keys()):
            if (args.debug):
                print ()
                print ("-----> %s <------" % baseSearch)
                print ("-----> %s <------" % searchFilters[baseSearchIndex-1])
                print ("-----> %s <------\n" % searchAttributes)
            try:
                ldap_results = ds.search(baseSearch, searchScope, searchFilters[baseSearchIndex-1], searchAttributes)
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
                result_sets[baseSearch] = result_set
            except ldap.FILTER_ERROR as e:
                print (f"ERROR: {e=}, {type(e)=}")
                print (f"FILTER: {searchFilters[baseSearchIndex-1]}")
                sys.exit(3)
            except Exception as e:
                print (f"ERROR: {e=}, {type(e)=}")
                sys.exit(3)

    ds.unbind_s()

    # Find the current max uidnumber in the local branch for the allowed range
    maxUidNumber = localUidAllowedRange[0]
    for local_entry in result_sets[baseSearches[2]]:
       for local_uid in local_entry:
           if ('uidnumber' in local_uid[1].keys()):
               currentUidNumber = int(local_uid[1]['uidnumber'][0])
               if (currentUidNumber > maxUidNumber and currentUidNumber < localUidAllowedRange[1]): maxUidNumber = currentUidNumber
    if (args.debug): print (f"Max local uidnumber: {maxUidNumber}")

    # Find people matching in the top branch but not present in the local branch
    add_user = []
    posix_add_user = []
    group_add_user = []
    user_count = [0,0,0,0]
    for top_entry in result_sets[baseSearches[0]]:
        for top_uid in top_entry:
            found = 0
            if (not args.force):
                for local_entry in result_sets[baseSearches[2]]:
                    for local_uid in local_entry:
                        if (top_uid[1]['uid'] == local_uid[1]['uid']):
                            found = 1
                            if ('uidnumber' not in local_uid[1].keys()):
                                posix_add_user.append((1,local_uid))
                                user_count[2] += 1
                            if (args.debug): print (f"Skipping user {local_uid[1]['uid'][0].decode('utf-8')}")
                            break
            if (top_uid[1]['uid'][0].decode('utf-8') not in localGroups[args.group[0]]):
                group_add_user.append((2,top_uid))
                user_count[3] += 1
            user_count[0] += 1
            if (found == 0):
                add_user.append((0,top_uid))
                user_count[1] += 1

    # Find posix attributes for people in the site and local branch
    posix_user_info = {}
    for site_entry in result_sets[baseSearches[1]]+result_sets[baseSearches[2]]:
        for site_uid in site_entry:
            uid = site_uid[1]['uid'][0].decode('utf-8')
            posix_user_info[uid] = { 'uidnumber': None, 'gidnumber': None }
            if ('uidnumber' in site_uid[1].keys()): posix_user_info[uid]['uidnumber'] = site_uid[1]['uidnumber'][0].decode('utf-8')
            if ('gidnumber' in site_uid[1].keys()): posix_user_info[uid]['gidnumber'] = site_uid[1]['gidnumber'][0].decode('utf-8')

    # Print summary statistics
    if (args.verbose):
        print (f"Total users: {user_count[0]}")
        print (f"New users: {user_count[1]}")
        print (f"Users with missing posix info: {user_count[2]}")
        print (f"Users with missing group: {user_count[3]}")

    # Open the output file if required
    if (args.output):
        outputFile = open(args.output[0],'w')

    # Loop over the users
    for user in add_user + posix_add_user + group_add_user:
        uid = user[1][1]['uid'][0].decode('utf-8')
        infnlinkeduuid = user[1][1]['infnlinkeduuid'][0].decode('utf-8')
        givenName = user[1][1]['givenName'][0].decode('utf-8')
        if (uid in posix_user_info.keys() and posix_user_info[uid]['uidnumber']):
                uidnumber = posix_user_info[uid]['uidnumber']
        else:
            maxUidNumber += 1
            uidnumber = maxUidNumber
        if (uid in posix_user_info.keys() and posix_user_info[uid]['gidnumber']):
            gidnumber = posix_user_info[uid]['gidnumber']
        else:
            gidnumber = args.gid[0]
        sn = user[1][1]['sn'][0].decode('utf-8')
        cn = user[1][1]['cn'][0].decode('utf-8')
        shell = args.shell[0]
        homeDirPath = homeDir % uid
        if ('infnKerberosPrincipal' in user[1][1].keys()):
            selectedPrincipal = user[1][1]['infnKerberosPrincipal'][0]
            if (args.debug): print (f"Initially selected Principal Kerberos: {selectedPrincipal}")
            for principal in user[1][1]['infnKerberosPrincipal'][1:]:
                if (principal.decode('utf-8').split('@')[1] == args.kerberos_realm[0]): selectedPrincipal = principal
            infnKerberosPrincipal = selectedPrincipal.decode('utf-8')
            if (args.debug): print (f"Selected Principal Kerberos: {selectedPrincipal}")
            KRBTOKEN='KRBPW'
        else:
            infnKerberosPrincipal = ""
            KRBTOKEN=''
        if ('mail' in user[1][1].keys()):
            mail = user[1][1]['mail'][0].decode('utf-8')
        else:
            print (f"User {user[1][1]['uid']} has not mail defined")
            sys.exit(20)
        if ('mailalternateaddress' in user[1][1].keys()):
            mailalternateaddress = b':'.join(user[1][1]['mailalternateaddress']).decode('utf-8')
        else:
            mailalternateaddress = ""

        # Build the ADD USER command
        if (user[0] == 0):
            COMMAND = f"ssh -p 57847 extuserserv@protoserv.infn.it ADD \"{local_branch}:{uid}:{infnlinkeduuid}:{givenName}:{sn}:{infnKerberosPrincipal}:{mail}:{mailalternateaddress}\""
            if (args.output):
                outputFile.write(f"{COMMAND}\n")
            else:
                print (COMMAND)

        # Build the ADD POSIX command
        if (user[0] in [0,1]):
            COMMAND = f"ssh -p 57847 extuserserv@protoserv.infn.it ADDPOSIX \"{local_branch}:{uid}:{KRBTOKEN}:{uidnumber}:{gidnumber}:{cn},,,:{homeDirPath}:{shell}\""
            if (args.output):
                outputFile.write(f"{COMMAND}\n")
            else:
                print (COMMAND)

        # Build the ADD GROUP command
        if (user[0] == 2):
            COMMAND = f"ssh -p 57847 groupserv@protoserv.infn.it ADDUSER \"{local_branch}.infn.it:{args.group[0]}:{uid}\""
            if (args.output):
                outputFile.write(f"{COMMAND}\n")
            else:
                print (COMMAND)
    # Clouse the output file if required
    if (args.output):
        outputFile.close()
