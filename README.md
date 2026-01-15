### Docker run

**Built image:**  
`docker build -t voice-cleaner .`

**Check (help):**  
`docker run voice-cleaner`

**Main launch:** 

*Linux / macOS*  
````
  docker run --rm \
  -v "$(pwd):/work" \
  -w /work \
  voice-cleaner \
  fixtures/input.mp4 out/clean.mp4
````

*Windows (PowerShell)*  
`docker run --rm -v "${PWD}:/work" -w /work voice-cleaner fixtures/input.mp4 out/clean.mp4`
