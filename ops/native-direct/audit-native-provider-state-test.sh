#!/usr/bin/env bash
# Read-only TEST audit of the *running* OpenCode Native, not a mock or Gateway DB.
# Outputs only provider IDs/model counts; no API keys, tokens, raw JSON or config.
set -euo pipefail
umask 077
systemctl is-active --quiet opencode-native-test.service || {
  echo "NATIVE_SERVICE_NOT_ACTIVE"; exit 1;
}
command -v curl >/dev/null
command -v perl >/dev/null
perl -MJSON::PP -e 'print "NATIVE_JSON_PARSER_READY\n"' >/dev/null
temp="$(mktemp -d)"
trap 'rm -rf -- "$temp"' EXIT
echo "NATIVE_INSPECTION_SOURCE=running OpenCode service via loopback Nginx, not Gateway"
for item in "provider 18097 /provider" "configured 18098 /config/providers"; do
  set -- $item
  label="$1"; port="$2"; route="$3"
  if curl --silent --show-error --fail --max-time 45 --connect-timeout 3 \
       -o "$temp/$label.json" "http://127.0.0.1:$port$route"; then
    echo "NATIVE_ROUTE_$label=HTTP_200"
  else
    echo "NATIVE_ROUTE_$label=FAILED"
    exit 1
  fi
done

perl -MJSON::PP -e '
  use strict; use warnings;
  local $/; my $payload=<>;
  my $d=decode_json($payload);
  die "Provider response invalid\n" unless ref($d) eq "HASH"
    && ref($d->{all}) eq "ARRAY" && ref($d->{connected}) eq "ARRAY";
  my @all=@{$d->{all}}; my @connected=@{$d->{connected}};
  my $models=0; my $free=0;
  for my $p (@all){
    next unless ref($p) eq "HASH";
    my $map=$p->{models};
    next unless ref($map) eq "HASH";
    $models+=scalar keys %$map;
    next unless ($p->{id}//"") eq "opencode";
    for my $m (values %$map){
      next unless ref($m) eq "HASH" && ref($m->{cost}) eq "HASH";
      $free++ if defined($m->{cost}{input}) && defined($m->{cost}{output})
        && $m->{cost}{input}==0 && $m->{cost}{output}==0;
    }
  }
  print "NATIVE_DISCOVERY_PROVIDERS=",scalar(@all),"\n";
  print "NATIVE_DISCOVERY_MODELS_TOTAL=$models\n";
  print "NATIVE_OPENCODE_FREE_MODELS=$free\n";
  print "NATIVE_REPORTED_CONNECTED_COUNT=",scalar(@connected),"\n";
  for my $id (@connected){
    next unless defined($id) && $id =~ /^[a-zA-Z0-9_.-]{1,80}$/;
    print "NATIVE_REPORTED_CONNECTED_ID=$id\n";
  }
  print "NOTE_CONNECTED_IS_NOT_VALIDATED_CREDENTIAL=yes\n";
' "$temp/provider.json"

perl -MJSON::PP -e '
  use strict; use warnings;
  local $/; my $payload=<>;
  my $d=decode_json($payload);
  die "Config/providers response invalid\n" unless ref($d) eq "HASH"
    && ref($d->{providers}) eq "ARRAY";
  my @all=@{$d->{providers}};
  print "NATIVE_CONFIGURED_PROVIDER_DEFINITIONS=",scalar(@all),"\n";
  for my $p (@all){
    next unless ref($p) eq "HASH";
    my $id=$p->{id}//"";
    next unless $id =~ /^[a-zA-Z0-9_.-]{1,80}$/;
    my $models=ref($p->{models}) eq "HASH" ? scalar(keys %{$p->{models}}) : 0;
    print "NATIVE_CONFIGURED_ID=$id MODELS=$models\n";
  }
  print "NOTE_CONFIGURED_IS_NOT_STORED_KEY=yes\n";
' "$temp/configured.json"

# 1.19.x may use auth.json outside the SQLite database.
# Only enumerate provider IDs from this known active Native data directory.
auth=/var/lib/opencode-native-test/data/opencode/auth.json
if test -r "$auth"; then
  perl -MJSON::PP -e '
    use strict; use warnings;
    local $/; my $payload=<>;
    my $d=decode_json($payload);
    die "Native auth metadata invalid\n" unless ref($d) eq "HASH";
    my @ids=grep { /^[a-zA-Z0-9_.-]{1,80}$/ } keys %$d;
    print "NATIVE_AUTH_JSON_SAVED_PROVIDER_COUNT=",scalar(@ids),"\n";
    print "NATIVE_AUTH_JSON_PROVIDER_ID=$_\n" for sort @ids;
  ' "$auth"
else
  echo "NATIVE_AUTH_JSON_AT_EXPECTED_PATH=NOT_READABLE_OR_MISSING"
fi
echo "NATIVE_AUDIT_COMPLETE_NO_MUTATION"
