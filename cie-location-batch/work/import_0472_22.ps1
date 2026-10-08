$env:EXAMDATA_DATA_DIR = 'C:/Users/weo/Desktop/api/examdata/.pytest_cache/callable-api'
& 'C:/Users/weo/Desktop/api/examdata/.venv/Scripts/examdata.exe' import-cie-index `
  'C:/Users/weo/Desktop/api/cie-location-batch/indexes/0472/2026-Jun-22/cie-index.json' `
  --qp 'C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf' `
  --ms 'C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2026-Jun-22/0472_s26_ms_22.pdf'
exit $LASTEXITCODE
