#!/usr/bin/env bash
# One-shot TEST acceptance of a real free model via the EXISTING Native server.
# No Python, Gateway AI, new process, persistent test DB or paid provider.
# Ephemeral Native session is deleted on completion; do not print responses.
set -euo pipefail
umask 077
ROOT=/var/lib/opencode-native-test/workspace
BASE=http://127.0.0.1:18098
MODEL=beam-free
test -d "$ROOT" || { echo "NATIVE_TEST_DIRECTORY_MISSING"; exit 1; }
systemctl is-active --quiet opencode-native-test.service
command -v perl >/dev/null && command -v curl >/dev/null
tmp="$(mktemp -d)"
sid=""
cleanup(){
  if test -n "$sid"; then
    curl --silent --show-error --max-time 8 --request DELETE \
      "$BASE/session/$sid?directory=$ROOT" >/dev/null || true
  fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT
echo "NATIVE_FREE_CHAT_SOURCE=live OpenCode Native via 18098; no Gateway/Python"
curl --silent --show-error --fail --max-time 25 \
  --request POST -H 'Content-Type: application/json' \
  --data '{"title":"[TEST] direct Native free-model connectivity probe"}' \
  "$BASE/session?directory=$ROOT" -o "$tmp/session.json"
sid="$(perl -MJSON::PP -0777 -ne 'my $d=decode_json($_);print $d->{id}//""' "$tmp/session.json")"
[[ "$sid" =~ ^ses_[A-Za-z0-9_-]+$ ]] || { echo "NATIVE_SESSION_CREATION_INVALID"; exit 1; }
echo "NATIVE_SESSION_CREATED_WITH_OPEN_CODE=yes"
curl --silent --show-error --fail --max-time 35 \
  --request POST -H 'Content-Type: application/json' \
  --data '{"model":{"providerID":"opencode","modelID":"beam-free"},"parts":[{"type":"text","text":"Please reply with exactly the word PONG and nothing else."}]}' \
  "$BASE/session/$sid/prompt_async?directory=$ROOT" -o /dev/null
echo "NATIVE_PROMPT_ASYNC_ACCEPTED=yes"
reply=no
for attempt in $(seq 1 25); do
  sleep 2
  curl --silent --show-error --fail --max-time 12 \
    "$BASE/session/$sid/message?directory=$ROOT" -o "$tmp/messages.json"
  result="$(perl -MJSON::PP -0777 -ne '
     my $messages=decode_json($_); die "Bad messages shape\n" unless ref($messages) eq "ARRAY";
     my ($ready,$errored)=(0,0);
     for my $row (@$messages){
       my $info=$row->{info}||{};
       next unless ($info->{role}//"") eq "assistant";
       $errored=1 if $info->{error};
       for my $part (@{$row->{parts}||[]}){
         next unless ($part->{type}//"") eq "text";
         my $body=$part->{text}//"";
         $ready=1 if length($body)>0 && !$info->{error};
       }
     }
     print $errored?"error":$ready?"ready":"pending";
  ' "$tmp/messages.json")"
  if test "$result" = ready; then reply=yes; break; fi
  if test "$result" = error; then echo "NATIVE_FREE_MODEL_RETURNED_ERROR"; exit 1; fi
done
if test "$reply" != yes; then echo "NATIVE_FREE_MODEL_NO_RESPONSE_WITHIN_PROBE"; exit 1; fi
echo "NATIVE_FREE_MODEL_ASSISTANT_RESPONSE=yes"
echo "NATIVE_FREE_MODEL_USED=opencode/beam-free"
echo "NATIVE_EPHEMERAL_SESSION_CLEANUP=scheduled"
