#!/bin/sh
# ipmikvm (part of ossobv/vcutil) // wdoekes/2019-2023 // Public Domain
#
# A wrapper to call the SuperMicro iKVM console bypassing Java browser
# plugins.
#
# Requirements: java, unzip, curl (and: awk, base64, grep, sed)
#
# Usage:
#
#   $ ipmikvm
#   Usage: ipmikvm [-u ADMIN] [-P ADMIN] IP.ADD.RE.SS
#
#   $ ipmikvm 10.11.12.13 -P otherpassword
#   (connects KVM console on IPMI device at 10.11.12.13)
#
#   $ ipmikvm manually-downloaded.jnlp
#   (skips login, uses local jnlp file)
#
# Config file ~/.config/ipmikvm/dict:
#
#   * * ADMIN ADMIN
#   * * ADMIN OTHERPASS
#   alias 1.2.3.4 ADMIN ADMIN
#
# This has been tested with:
# - JViewer-1.46
# - iKVM__V1.69.19.0x0
# - ...
# - iKVM__V1.69.42.0x0
#
# This has been tried with (but failed):
# - JViewer-unknown-version that comes with Quanta BMC
#
# See also: ipmiview
#
test -z "$HOME" && echo 'missing $HOME' && exit 1
set -u
APP_CACHE_DIR="$HOME/.local/lib/ipmikvm"

IP=
USER=
PASS=
USERS='ADMIN '
PASSES='ADMIN '

# Alter this list with if you get more apparent ports when using ssh proxy:
# http(80), https(443), ipmi(623), vnc(5900)
PROXY_PORT_MAPPING='80:5980 443:5943 623:5923 5900:5959'
PROXY_IP=  # dynamic?

# Use getopt(1) to reorder arguments
eval set --"$(getopt -- 'hu:P:L:' "$@")"

usage() {
    test ${1:-1} -ne 0 && exec >&2  # non-zero? write to stderr
    echo "Usage: $0 [-u ADMIN] [-P ADMIN] IP.ADD.RE.SS"
    echo
    echo "If you're setting up an ssh tunnel, you can specify a local IP"
    echo "like 127.75.86.77 and do this:"
    echo "  ssh -L 127.0.0.2:5980:IP.ADD.RE.SS:443 PROXY_HOST"
    echo "  $0 -L 1 IP.ADD.RE.SS"
    echo "  (or)"
    echo "  $0 -L 127.0.0.2 IP.ADD.RE.SS"
    echo
    echo "Usernames, passwords and machine aliases may be specified in"
    echo "~/.config/ipmikvm/dict - as ALIAS ADDRESS USER PASS - one per"
    echo "line. When ALIAS and ADDRESS are *, the USER and PASS will be"
    echo "tried consecutively for (otherwise) unmatched aliases/addresses."
    exit ${1:-1}
}

as_http() {
    echo "$1" | sed -e 's#^https://\([^:/]*\):443#http://\1#;s#^https:#http:#'
}

curl() {
    local url="$1"; shift
    if test -n "$PROXY_IP"; then
        url=$(echo "$url" | sed -e '
            s#^http://\([^/]*\)#http://'$PROXY_IP$WITH_HTTP_PORT'#
            s#^https://\([^/]*\)#https://'$PROXY_IP$WITH_HTTPS_PORT'#')
    fi
    command curl "$url" "$@"
}

while getopts 'hu:P:L:' OPTION; do
    case "$OPTION" in
    h) usage 0;;
    u) USER=$OPTARG;;
    P) PASS=$OPTARG;;
    L) PROXY_IP=$OPTARG;;
    #v) PROXY_PORT_MAPPING=$OPTARG;;
    ?) usage 1;;
    esac
done
shift $((OPTIND - 1))

test $# -ne 1 && usage
IP=${1:-}; shift
test -z "$IP" && usage

# Try the aliases/password file.
DICT="$HOME/.config/ipmikvm/dict"
if test -s "$DICT"; then
    # Alias match
    LINES=$(awk "/^ *[^#]/{if(NF>=4&&(\$1==\"$IP\"||\$2==\"$IP\")){
        print \$0;exit}}" "$DICT")
    if test -n "$LINES"; then
        IP=$(echo "$LINES" | awk '{print $2}')
        test -z "$USER" && USER=$(echo "$LINES" | awk '{print $3}')
        test -z "$PASS" && PASS=$(echo "$LINES" | awk '{print $4}')
    elif test -z "$USER" && test -z "$PASS"; then
        # No user/pass supplied. Then get all the * * matches.
        USERS=$(awk '/^ *[^#]/{if(NF>=4&&$1=="*"&&$2=="*"){
            printf "%s ", $3}}' "$DICT")
        PASSES=$(awk '/^ *[^#]/{if(NF>=4&&$1=="*"&&$2=="*"){
            printf "%s ", $4}}' "$DICT")
    fi
fi
test -n "$USER" && USERS="$USER "; USER=
test -n "$PASS" && PASSES="$PASS "; PASS=

show_proxy_ssh() {
    local ip="$1"; shift
    local proxy_ip="$1"; shift;
    echo "Please run the following in another shell:"
    echo -n "# ssh"
    for port in $PROXY_PORT_MAPPING; do
        local real=${port%:*}
        local proxy=${port#*:}
        echo -n " -L $proxy_ip:$proxy:$ip:$real"
    done
    echo " PROXY_HOST"
    echo -n "(press enter when ready)" >&2
    local discard
    read discard
}

if test -n "$PROXY_IP"; then
    # Fix HTTP and HTTPS replacements
    test "${PROXY_IP%.*}" = "$PROXY_IP" && PROXY_IP=127.75.86.77
    for port in $PROXY_PORT_MAPPING; do
        case ${port%:*} in
        80) WITH_HTTP_PORT=:${port#80\:};;
        443) WITH_HTTPS_PORT=:${port#443\:};;
        esac
    done
    # Show and wait for proxy action
    show_proxy_ssh $IP $PROXY_IP
else
    WITH_HTTP_PORT=
    WITH_HTTPS_PORT=
fi


get_launch_jnlp() {
    local management_ip="$1"
    local users="$2"
    local passes="$3"

    local url="https://$management_ip"
    local local_append=''
    local temp=$(mktemp)

    until test -z "$users"; do
        local user=${users%% *}; users=${users#* }
        local pass=${passes%% *}; passes=${passes#* }
        echo "attempting login on '$management_ip' with user $user" >&2

        # Add --compressed. The Quanta BMC will send gzipped regardless
        # of provided support.
        local data="$(curl "$url" --fail -LksS --cookie-jar "$temp" \
            --compressed)"
        local ret=$?
        if test $ret -eq 0 && echo "$data" |
                grep -q '<title>Quanta Cloud</title>'; then
            _get_launch_jnlp_quanta "$management_ip" "$user $users" \
                "$pass $passes" "$temp"
            rm "$temp"
            return
        elif test $ret -ne 0 || ! echo "$data" | grep -q '<form '; then
            echo "unexpected login page on address '$management_ip': $data" >&2
            data=
            if test "${url#https:}" != "$url"; then
                url=$(as_http "$url")
                echo "retrying without ssl on $url" >&2
                local_append='<!-- DISABLED_SSL -->'
                data=$(curl "$url" --fail -LksS --cookie-jar "$temp")
                if test $? -ne 0 || ! echo "$data" | grep -q '<form '; then
                    echo "sad times" >&2
                    data=
                fi
            fi
            if test -z "$data"; then
                false
                break
            fi
        fi
        local use_base64=$(echo "$data" | grep -q '=.*btoa' && echo 1)

        if test -n "$use_base64"; then
            user=$(echo -n "$user" | base64 -w0 | sed -e 's/=/%3D/g;s/+/%2B/g')
            pass=$(echo -n "$pass" | base64 -w0 | sed -e 's/=/%3D/g;s/+/%2B/g')
        fi
        data=$(test -n "$data" &&
          curl "$url/cgi/login.cgi" --fail -LksS --cookie "$temp" \
            --cookie-jar "$temp" -XPOST --data "name=$user&pwd=$pass&check=00")
        local ret=$?
        local fail_heur=0
        if test $ret -eq 0; then
            local ok_heur=$(echo "$data" |
                grep -cF 'url_redirect.cgi?url_name=mainmenu')
            fail_heur=$(echo "$data" | grep -ciE \
                "url_redirect[.]cgi[?]url_name=login_alert|alert[(]|\
<META HTTP-EQUIV=\"refresh\" CONTENT=\"0;URL=/\">")
            if test $ok_heur -gt 0 && test $fail_heur -gt 0; then
                echo "login page looks like success AND failure: $data" 2>&1
                rm "$temp"
                exit 1
            fi
            if test $fail_heur -gt 0; then
                ret=1
            fi
        fi
        test $ret -eq 0 && break
        echo "login failure ($fail_heur markers on page)" >&2
        data=
        false
    done

    if test -n "$data"; then
        for url_name in man_ikvm ikvm; do
            data=$(curl \
                "$url/cgi/url_redirect.cgi?url_name=$url_name&url_type=jwsk" \
                --fail -LksS --cookie "$temp" \
                -H "Referer: $url/cgi/url_redirect.cgi?url_name=man_ikvm")
            test $? -ne 0 && echo "$data" | grep -q '^<jnlp spec=' && break
        done
        if ! echo "$data" | grep -q '^<jnlp spec='; then
            echo "unexpected jnlp page: $data" >&2
            data=
        fi
    fi
    rm "$temp"
    test -n "$data" && echo "$data$local_append"
}
# SYNOPSIS: get_launch_jnlp 10.x.x.x USERNAME PASSWORD

_get_launch_jnlp_quanta() {
    local management_ip="$1"
    local users="$2"
    local passes="$3"
    local temp="$4"

    local url="https://$management_ip/api"
    local data
    local csrf

    until test -z "$users"; do
        local user=${users%% *}; users=${users#* }
        local pass=${passes%% *}; passes=${passes#* }
        echo "attempting Quanta login on '$url' with user $user" >&2
        data=$(curl "$url/api/session" --fail -LksS \
            --cookie "$temp" --cookie-jar "$temp" --compressed \
            -XPOST --data "username=$user&password=$pass")
        local ret=$?
        if test $ret -eq 0; then
            echo "got Quanta login: $data" >&2
            # { "ok": 0, "privilege": 4, "extendedpriv": 256,
            #   "racsession_id": 9, "remote_addr": "10.x.x.1",
            #   "server_name": "10.x.x.212", "server_addr":
            #   "10.x.x.212", "HTTPSEnabled": 1, "CSRFToken": "ZxEvkl0S" }
            csrf=$(printf '%s\n' "$data" | jq -r .CSRFToken)
            echo "fetching kvmjnlp with CSRF $csrf..." >&2
            data=$(curl "$url/kvmjnlp?&JNLPSTR=JViewer&HostOrIp=1" --fail \
                -LksS --cookie "$temp" --cookie-jar "$temp" --compressed \
                -H "X-CSRFTOKEN: $csrf")
            printf '%s\n' "$data"
            return
        fi
    done
    false
}

make_local_path() {
    local path="$1"
    echo "$path" | sed -e 's#.*://##;s#^/*##;s#:#%3A#g;s#[.][.]*#.#g;'
}
# SYNOPSIS: make_local_path PATH_MAYBE_WITH_HTTPS

get_app_jar() {
    local launch_jnlp="$1"
    local app_cache_dir="$2"

    local app_jar="$(get_jars "$launch_jnlp" | head -n1)"   # first jar
    app_jar=$(make_local_path "$app_jar")                   # as local path
    if test -z "$app_jar"; then
        echo "cannot find application jar name in jnlp: $launch_jnlp" >&2
        exit 1
    fi
    local jar_base="$(basename "$app_jar")" # iKVM__V1.69.31.0x0.jar
    local jar_base="${jar_base%.jar}"   # iKVM__V1.69.31.0x0

    local app_cache_dir
    case $jar_base in
    JViewer)
        local codebase_ip
        codebase_ip=$(printf '%s\n' "$launch_jnlp" | sed -e '
            /codebase="/!d
            s@.* codebase="[^/]*//@@;s@:.*@@;s@/.*@@' | head -n1)
        app_cache_dir="$app_cache_dir/$jar_base-$codebase_ip"
        ;;
    *)
        app_cache_dir="$app_cache_dir/$jar_base"
        ;;
    esac

    umask 0077  # storing latest.jnlp here; might contain temp passwords
    test -d "$app_cache_dir" || mkdir -p "$app_cache_dir" || exit 1
    echo "$launch_jnlp" >"$app_cache_dir/latest.jnlp"
    if ! test -f "$app_cache_dir/$app_jar"; then
        install_ikvm_application "$launch_jnlp" "$app_cache_dir" >&2 || exit 1
        test -f "$app_cache_dir/$app_jar" || exit 1
    fi
    echo "$app_cache_dir/$app_jar"
}
# SYNOPSIS: get_app_jar JNLP_DATA APP_CACHE_DIR

get_app_class() {
    echo "$1" | sed -ne 's/.*<application-desc .*main-class="\([^"]*\)".*/\1/p'
}
# SYNOPSIS: get_app_class JNLP_DATA

get_jars() {
    echo "$1" | sed -e '
      /<jar /!d
      s#.* href="\([^"]*\).jar".*version="\([^"]*\)".*#\1__V\2.jar#
      s#.* href="\([^"]*\).jar".*#\1.jar#'
}
# SYNOPSIS: get_jars JNLP_DATA

get_arguments() {
    local certarg="$(echo "$1" | tr '\n' '|' | sed -e '
      /-----BEGIN CERTIFICATE/!d
      s/.*<argument>\(-----BEGIN CERTIFICATE[^<]*\)<.*/\1/
      '"s/['\"$]//g"';s/|/${LF}/g')"
    echo "$1" |
      sed -e '/<argument>/!d;s#.*<argument>\([^<]*\)</argument>.*#\1#' |
      sed -e "s/['\"$]//g;s/.*/'&'/" |
      sed -e "s!^'[[:blank:]]*<argument>-----BEGIN.*!\"$certarg\"!g"
}
# SYNOPSIS: get_arguments JNLP_DATA  # dumps quotes args to stdout
# DESCRIPTION: fetches every <argument>...</argument> from the data
#   and echoes them surrounded by quotes, so <argument>1</argument>
#   becomes '1'. For the optional certificate multiline argument, an
#   ${LF} variable is added, so we get a linefeed in the eval.
# USAGE: LF=$'\n'; eval set -- $(get_arguments "$JNLP_DATA")

replace_arguments() {
    local sed_script=''
    for port in "$@"; do
        local real=${port%:*}
        local proxy=${port#*:}
        sed_script="${sed_script}s/^'$real'\$/'$proxy'/;"
    done
    sed -e "${sed_script%;}"  # s/^'5900'$/'5959'/ etc..
}
# SYNOPSIS: replace_arguments PORT_MAPPINGS
# DESCRIPTION: replaces arguments
# USAGE: get_arguments ... | replace_arguments 80:5980 443:5943 623:5923 ...

exec_app() {
    local jar="$1"; shift
    local class="$1"; shift
    if test -z "$class"; then
        class=$(unzip -c "$jar" META-INF/MANIFEST.MF |
            tr -d '\r' | tr '\t' ' ' |
            awk '/^Main-Class *:/{print $2}')
        echo "found Main-Class $class in $jar" >&2
    fi
    # iKVM
    #*/iKVM*.jar) class=tw.com.aten.ikvm.KVMMain;;
    # Redirection Viewer v1.46
    #*/JViewer.jar) class=com.ami.kvm.jviewer.JViewer;;
    if test -z "$class"; then
        echo "Unknown entrypoint in $jar" >&2
        exit 1
    fi
    set -x
    exec java -Djava.library.path="${jar%/*}" -cp "$jar" "$class" "$@"
}
# SYNOPSIS: exec_app JAR CLASS 10.x.x.x KVM_USERNAME KVM_PASSWORD

install_ikvm_application() {
    local launch_jnlp="$1"
    local destdir="$2"

    set -e
    local codebase=$(
      echo "$launch_jnlp" | sed -e '/<jnlp /!d;s/.* codebase="//;s/".*//')
    if echo "$launch_jnlp" | grep -q DISABLED_SSL; then
        codebase=$(as_http "$codebase")
    fi
    test "${codebase%/}" = "$codebase" || codebase="${codebase%/}"
    local jars="$(get_jars "$launch_jnlp")"
    case "$(uname -s)" in
        Linux) local libprefix='\(liblinux.*x86_64\|Linux.*x86_64\|Linux64\)';;
        Darwin) local libprefix='\(libmac.*x86_64\|Mac.*x86_64\|Mac64\)';;
        *) echo "Unknown platform: $(uname -s)" >&2; exit 1;;
    esac
    local nativelibs=$(
      echo "$launch_jnlp" | sed -e '
        /<nativelib.*'$libprefix'/!d
        s#.* href="\([^"]*\).jar".*version="\([^"]*\)".*#\1__V\2.jar#
        s#.* href="\([^"]*\).jar".*#\1.jar#' | sort -u)
    set -x
    mkdir -p "$destdir"
    cd "$destdir"
    local path local_path remote_path
    for path in $jars $nativelibs; do
        local_path="$(make_local_path "$path")"
        remote_path=$path
        if test "${remote_path%//*}" = "$remote_path"; then
            remote_path="$codebase/$remote_path"  # add "https://" to path
        fi
        test "${local_path%/*}" = "$local_path" || mkdir -p "${local_path%/*}"
        if curl "$remote_path" -sS --fail -ko "$local_path" &&
                file --brief --mime "$local_path" |
                grep -E '^application/(java-archive|zip)'; then
            :
        elif curl "$remote_path.pack.gz" -sS --fail -ko "$local_path.pack.gz" &&
                file --brief --mime "$local_path.pack.gz" |
                grep -E '^application/gzip' &&
                gunzip "$local_path.pack.gz" &&
                unpack200 "$local_path.pack" "$local_path"; then
            :
        else
            echo "$launch_jnlp"
            false
        fi
    done
    for path in $nativelibs; do
        local_path="$(make_local_path "$path")"
        if test -f "$local_path"; then
            ( cd "$(dirname "$local_path")" &&
                unzip -o "$(basename "$local_path")" -x 'META-INF/*' )
        fi
    done
    set +x
    set +e
}
# SYNOPSIS: install_ikvm_application JNLP_DATA DESTDIR

if test "${IP%.jnlp}" != "$IP" -a -f "$IP"; then
    echo "(assuming $IP is the JNLP file)" >&2
    JNLP=$(cat "$IP")
else
    JNLP=$(get_launch_jnlp "$IP" "$USERS" "$PASSES")
    test -z "$JNLP" && echo "Failed to get launch.jnlp" >&2 && exit 1
fi

JAR=$(get_app_jar "$JNLP" "$APP_CACHE_DIR")
test -z "$JAR" && echo "Failed to get iKVM*.jar/JViewer*.jar" >&2 && exit 1
CLASS=$(get_app_class "$JNLP")  # might be blank

# Load quoted arguments (including multiline args)
# (Note that LF=$'\n' works with bash, but LF='\n' works with dash.)
LF='
'
if test -n "$PROXY_IP"; then
    # Fetch likely ports. If they are not in the $PROXY_PORT_MAPPING
    # then they may need to be added.
    possible_ports=$(get_arguments "$JNLP" | sed -ne "
        s/^'0'\$//;s/^'\([0-9]\+\)'$/\1/p" | sort -un )
    echo "(remote probably uses" $possible_ports "for ports)" >&2
    echo "(we remapped" $PROXY_PORT_MAPPING "ports)" >&2
    # Replace IP with our selected IP.
    # By using a regex instead of $IP, we can use a prefetched jnlp file here.
    eval set -- $(get_arguments "$JNLP" | replace_arguments \
        '\([0-9]\+[.]\)\{3\}[0-9]\+':$PROXY_IP $PROXY_PORT_MAPPING)
else
    eval set -- $(get_arguments "$JNLP")
fi

exec_app "$JAR" "$CLASS" "$@"
