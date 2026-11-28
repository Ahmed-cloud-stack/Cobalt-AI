#!/usr/bin/env bash
# Docker fallback for task images whose editable files live under /app.
set -euo pipefail
task=$(realpath "${1:?Usage: replay.sh TASK_DIR IMAGE MODE NEW_RESULT_DIR [SEALED_APP_OVERLAY]}")
image=${2:?Build IMAGE from the task environment directory first}
mode=${3:?Choose oracle, nop, or blind}
result=$(realpath -m "${4:?Supply a new result directory}")
flags=(-v "$task/tests:/creator-private/fixture:ro")
case "$mode" in
    oracle) flags+=(-v "$task/solution:/solution:ro");;
    nop) ;;
    blind)
        overlay=$(realpath "${5:?Supply a directory of edited /app files and generated outputs}")
        test -d "$overlay"
        if find "$overlay" -type l -print -quit | read -r ignored; then
            echo "Rejecting a symlink in the submission" >&2
            exit 1
        fi
        flags+=(-v "$overlay:/submission:ro")
        ;;
    *) echo "Invalid mode $mode" >&2; exit 1;;
esac
mkdir "$result"
if docker run --rm --network none --cpus "${TASK_CPUS:-2}" --memory "${TASK_MEMORY:-4096m}" \
    "${flags[@]}" "$image" sh -ec '
        umask 022
        chmod 700 /creator-private
        cp -r /creator-private/fixture /tests
        chmod 700 /tests
        case "$1" in
            oracle) /solution/solve.sh;;
            blind) tar -C /submission --mode=u+rwX,go+rX -cf /tmp/submission.tar . && tar -C /app -xf /tmp/submission.tar;;
        esac
        /tests/test.sh
        printf "reward="
        cat /logs/verifier/reward.txt
    ' sh "$mode" >"$result/verifier.log" 2>&1; then
    case "$(tail -n 1 "$result/verifier.log")" in
        reward=0) printf "0\n" > "$result/reward.txt";;
        reward=1) printf "1\n" > "$result/reward.txt";;
        *) echo "Missing binary reward" >&2; exit 1;;
    esac
    tail -n 2 "$result/verifier.log"
else
    echo "Verifier infrastructure failed. Inspect $result/verifier.log" >&2
    exit 1
fi
