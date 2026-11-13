#!/bin/sh
set -eu
test "$(id -u)" = 0
export DEBIAN_FRONTEND=noninteractive
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
apt-get -o Acquire::Retries=0 -o Acquire::http::Timeout=45 update
apt-get -o Acquire::Retries=0 -o Acquire::http::Timeout=45 install -y --no-install-recommends build-essential autoconf automake libtool pkg-config git patch python3 xz-utils ca-certificates passwd util-linux libssl-dev tcl-dev libexpat1-dev libpcre3-dev libcap-dev bison flex libluajit2-5.1-dev libmaxminddb-dev libboost-dev libxml2-dev libncurses-dev libcurl4-openssl-dev libhiredis-dev libkyotocabinet-dev libmemcached-dev libbrotli-dev libcrypto++-dev libjansson-dev libcjose-dev libyaml-cpp-dev netbase
apt-get clean
if ! getent passwd 1000 >/dev/null; then
    groupadd -g 1000 ubuntu
    useradd -m -u 1000 -g 1000 -d /home/ubuntu -s /bin/sh ubuntu
fi
test "$(getent passwd 1000 | cut -d: -f1)" = ubuntu
install -d -o 1000 -g 1000 /home/ubuntu
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > /workspace/dependencies.tsv
touch /workspace/dependencies.ready
# The host verifies the exact owned container and disconnects its network first.
count=0
while ! test -f /workspace/build.start; do
    count=$((count + 1))
    test "$count" -le 300
    sleep 1
done
exec runuser -u ubuntu -- env HOME=/home/ubuntu USER=ubuntu LOGNAME=ubuntu PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 python3 /control/poc003_fresh_neutral_core_builder_v1.py
