# Accepted implementation and actual main

Actual code 4451370972a4b9ce7095950060f2f72b64df711e / actual last code merge PR90 03496c353a1057086cb2d26eb36c5bbc497f730c. Native15 checks/630 tests1133.31s zero FES; original same-headCI662630 tests1557.86s and full28 steps passed. Actual main pushCI663630 tests passed and has its independent acceptance, preserved separately. No native main full-suite rerun is claimed.

raw-results.bundle.json records each exact original physical byte length/SHA256. Verify each part SHA256, concatenate stripped part text in listed order, base64 decode and zlib decompress; then compare the raw size/hash. Splitting transport chunks changes no original bytes and avoids oversized connector requests. Every original checker command and JUnit is losslessly recoverable.

This archive is historical execution bound only to code445 and actualmain034. Current Review source verification, its full same-headCI and independent integration approval remain pending. Normal Completion, GZ021 and full local V1 are not complete.
