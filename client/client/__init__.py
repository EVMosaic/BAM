import requests

with open('config.json', 'r') as config:
    import json
    config = json.load(config)

def request_url(path):
    return ('%s%s' % (config['BAM_SERVER'], path))


#payload = {'path': ''}
#r = requests.get(request_url('/files'), params=payload, auth=('bam', 'bam'))
#print (r.json())

payload = {'filepath': 'video.mp4'}
r = requests.get(request_url('/file'), params=payload, auth=('bam', 'bam'), stream=True)
local_filename = payload['filepath'].split('/')[-1]

with open(local_filename, 'wb') as f:
    for chunk in r.iter_content(chunk_size=1024): 
        if chunk: # filter out keep-alive new chunks
            f.write(chunk)
            f.flush()
print(local_filename)
