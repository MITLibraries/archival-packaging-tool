# Lambda Request / Response Payload Specifications

This tool will be deployed as an AWS Lambda, and the expected primary way of invoking it will be via HTTP `POST` requests.  The following details the structure of the request payload sent to the Lambda and the response payload returned.

## Request Payload

Example JSON payload sent via a `POST` request:
```json
{
    "challenge_secret": "abc123def456",
    "verbose": true,
    "metadata": {
      "Contact-Name": "Winding River",
      "External-Identifier": "abc123"
    },
    "input_files": [
        {
            "uri": "s3://my-bucket/apt-testing/dogs.tiff",
            "filepath": "dogs.tiff",            
            "checksums":{
              "sha256": "23bcd2d83d4c0f270640ec65cbeb61a1784856255c3c98dd25ec340453458348s",
            }
        },
				{
            "uri": "s3://another-bucket/apt-testing/CATS.PDF",
            "filepath": "cats.pdf"            
        },
        {
            "uri": "s3://my-bucket/apt-testing/metadata.csv",
            "filepath": "metadata/metadata.csv",            
            "checksums":{
              "md5": "9f81f3c07476a0d97f6793673dd8e475"
            }
        }
    ],
    "checksums_to_generate":[
      "md5",
      "sha256"
    ],
    "output_zip_s3_uri": "s3://my-bucket/apt-testing/test-one-medium.zip",
    "compress_zip": true
}
```
### Fields
- `challenge_secret`: **REQUIRED** shared, secret string confirmed by the Lambda before processing request
- `verbose`: **OPTIONAL** boolean for verbose logging and response
- `metadata`: **OPTIONAL** object of key:value pairs that getting written as metadata to `bagit-info.txt`
- `input_files`: **REQUIRED** array of objects that define what files should be downloaded and added to the final bagit zipfile
  - `uri`: **REQUIRED** location to download the file from
  - `filepath`: **REQUIRED** desired final filepath in the bagit zip file, relative to the root of the bag    - 
    - e.g. `hello.txt` will end up at `/data/hello.txt` in the final bag, where `my/custom/path/goodbye.txt` would end up date`/data/my/custom/path/goodbye.txt`
    - This provides a way to rename (filename) and organize (path) the file that was downloaded and written to the bag.
  - `checksums`: **OPTIONAL** object of `<checksum name>: <checksum value>`
    - If included, an error will be raised if the checksums generated during creation of the bag do not match this checksum
    - Only checked if the checksum algorithm in this object is also included in the request root `checksums` field as well, instructing Bagit to generate a checksum for those algorithms
    - If the checksum algorithm does not match a supported algorithm as defined below an error will be raised
- `checksums_to_generate`: **OPTIONAL** list of checksums for the bagit library to create for each file when creating the bag
  - Default: `["md5", "sha256"]`
  - Supported checksums (as influenced by the underlying [python bagit library](https://github.com/LibraryOfCongress/bagit-python)): `[blake2b, blake2s, md5, sha1, sha224, sha256, sha3_224, sha3_256, sha3_384, sha3_512, sha384, sha512, shake_128, shake_256]`
- `output_zip_s3_uri`: **REQUIRED** location where the final bagit zipfile will be written to
- `compress_zip`: **OPTIONAL** boolean to use compression when creating the Bagit zipfile
  - Default: `true`

### Example Notes

- All three objects use the `input_files.checksum` field differently.  The first file `dogs.tiff` has a known `sha256` and passes it, `cats.pdf` has no prior known checksums so the field is omitted, and `metadata.csv` passes an MD5.
- Note that input files are coming from two different buckets, `my-bucket` and `another-bucket`; this is allowed.

## Response Payload

Example JSON response:
```json
{
    "elapsed": 4.12,
    "success": true,
    "error": null,
    "bag": {
        "entries": {
            "manifest-sha512.txt": {
                "sha256": "434252ceed4c0c0a7c7bd444af4a0634efcd3a32c4f46d8ff68d9ecc5fc184fe",
                "md5": "e0120e535107e62f73ac2e9f7a735865"
            },
            "bag-info.txt": {
                "sha256": "0f8ec18f8016b84d46c05270263205149e62af1327f3ea23a91c0e493b6f4194",
                "md5": "1dcf3f47e610490ba54cce51870ec325"
            },
            "manifest-sha256.txt": {
                "sha256": "f546d266681c2078cb5164b3f5a8cba228114dda93acc719a27a60eae74e8a3f",
                "md5": "0fc2001630558bd4b870465960829979"
            },
            "data/dogs.tiff": {
                "sha256": "23bcd2d83d4c0f270640ec65cbeb61a1784856255c3c98dd25ec340453458348",
                "md5": "d28d2d3560fa76f0dbb1a452f8c38169"
            },
						"data/cats.pdf": {
                "sha256": "d936608baaacc6b762c14b0c356026fba3b84e77d5b22e86f2fc29d3da09c675",
                "md5": "0832c1202da8d382318e329a7c133ea0"
            },
						"data/metadata/metadata.csv": {
                "sha256": "45447b7afbd5e544f7d0f1df0fccd26014d9850130abd3f020b89ff96b82079f",
                "md5": "9f81f3c07476a0d97f6793673dd8e475"
            },
            "bagit.txt": {
                "sha256": "e91f941be5973ff71f1dccbdd1a32d598881893a7f21be516aca743da38b1689",
                "md5": "9e5ad981e0d29adc278f6a294b8c2aca"
            },
            "manifest-md5.txt": {
                "sha256": "e735a9f5a3ee8fb491630a49a70e63a1acdf7d6b08a1763f329e82ff5956b212",
                "md5": "d5c3f14e7528c05184aaba3566ba3061"
            }
        }
    },
    "output_zip_s3_uri": "s3://my-bucket/apt-testing/test-one-medium.zip"
}
```

### Fields

- `elapsed`: Time in seconds to create the bag (does NOT include Lambda spin up and network request/response time)
- `success`: Boolean value of overall success of bag creation; no catastrophic errors
- `error`: If an error occurred during bag creation, a string representation of the error.  May be null.
- `bag`: An object representing the final bag created
  - `entries`: An object listing all files in the bag with any checksums generated for them
    - The use of "entries" comes from the python bagit library where this data comes from.
  - `output_zip_s3_uri`: Location of the generated bagit zipfile.
    - This is likely already known as part of the request payload.