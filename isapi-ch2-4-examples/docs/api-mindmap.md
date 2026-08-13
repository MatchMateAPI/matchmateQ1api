# ISAPI Chapters 2–4 API Integration Mind Map (Overview / ISAPI Framework / Quick Start)

> **Purpose**: a guide for users or AI to understand, integrate, and develop against ISAPI. Every API node follows four elements — **Definition | Type | How to Call | Example**.
> **Mind map structure**: Chapter → Section → API/Concept → the four elements. A companion interactive mind map page is available alongside this document.

---

# Chapter 2 — Overview

## 2.1 Protocol Positioning (What ISAPI Is)

- **Definition**
  - ISAPI = Intelligent Security API, an **HTTP-based application-layer protocol** using the **REST architecture**, enabling communication between security devices (cameras, DVRs, NVRs, etc.) and platforms/client software
  - Created in 2013, now with **11,000+ interfaces**, covering device management, vehicle recognition, parking, face intelligence, access control, recording/broadcast control, etc., applied across public security, justice, transportation, fire safety, education and more
- **Communication model (type)**
  - **Client/Server mode**: the device acts as the **server** listening on a fixed port; the user program acts as the **client** that actively logs in to the device
  - Prerequisites: the device must have a **fixed IP address**, and client requests must be able to reach the server
  - ISAPI inherits all HTTP specifications and features
- **Companion protocols (call relationships)**
  - **SADP** (Search Active Device Protocol): multicast-based, handles **device discovery and activation**
  - **RTSP** (Real Time Streaming Protocol): TCP/UDP-based, handles **live preview and playback**; Hikvision extends RTSP with a **Metadata** scheme (synchronizes intelligent structured data with the stream; compatible with the RTSP standard)

## 2.2 Applicable Products

- Fixed network cameras, 2-series smart network cameras (DS-2CD2xxx / DS-2XA2xxx series; see the model list in Section 2.2 of the original document)

## 2.3 Terms and Definitions (Must-Read for Integration)

- **Event**: information actively reported by the device, requiring real-time handling; can be cached during network outages and re-reported after recovery
- **Fortify (arming)**: the client proactively establishes an event-upload connection to the device, over which the device pushes events
  - **Subscribed**: the client specifies an event list; the device only sends listed events
  - **Unsubscribed**: the device sends all event types
- **Listen**: the platform opens a listening service on its own local IP/port; when an alarm occurs, the device **actively connects to the platform port**, sends the message, then closes the connection
- **Listening host**: the platform that runs the listening service and receives device events
- **Center**: an independent service or service group (at least one device access service + one or more application platforms)
- **Push mode / Pull mode**: the device actively pushes / the center actively pulls
- **VMD (motion detection)**: detects image changes in a defined video region (person walking by, camera moved, etc.), reports alarms, and can trigger recording and alarm outputs
- **Video shelter / TOF shelter**: alarms raised when a defined region is artificially covered / when the camera's infrared reflection detects a close-range covering object
- **TFS (Traffic Forensics System)**: supports automatic detection and evidence capture for up to 4 lanes — illegal parking, wrong-way driving, U-turns, line-crossing, lane changes, motor vehicles in non-motor lanes — with real-time alarm reporting (difference: traffic event detection only detects; TFS records violation details such as background image, close-up image, vehicle image, and plate number)
- Others: edge node device (camera), edge domain device (NVR), firmware identification code (matches an upgrade package to a device), viewshed

## 2.4 Symbols and Abbreviations (Quick Reference)

| Abbrev. | Meaning | Abbrev. | Meaning |
|---|---|---|---|
| ISAPI | HTTP RESTful device access protocol | ISUP | Intelligent Security Uplink Protocol (device-initiated registration) |
| HEOP | Hikvision Embedded Open Platform (3rd-party APP runtime) | HPC | Hybrid/cloud business platform |
| RTSP | Real Time Streaming Protocol (RFC 7826) | SDP | Session Description Protocol |
| ANPR | Automatic Number Plate Recognition | TFS | Traffic Forensics System |
| VMD | Motion detection technology | PIR | Passive Infrared Detector |
| OSD | On-screen display (text overlay) | TOF | Time of Flight (depth sensing) |
| CMS / AMS | Central Management Server / Alarm Manage Server | NVR / IPC | Network Video Recorder / IP Camera |
| GB35114 | China national standard for video surveillance networking information security | HC | Mobile client (handheld) |

---
# Chapter 3 — ISAPI Framework

## 3.1 Overview

- ISAPI = HTTP-based communication protocol + the RTSP streaming standard (with the Metadata extension); together they form the ISAPI system

## 3.2 Activation (3 APIs + SADP Alternative)

> Purpose of activation: ensures the customer completes **initial password setup** with a password that complies with security rules; **device functions are usable only after activation**. Prerequisites: the device IP is known and network connectivity exists. The device's web page also activates via the ISAPI flow.
> Base operations: `bytesToHexstring` (N bytes → 2N-char hex string), `hexStringToBytes` (inverse).

### ① `GET /SDK/activateStatus`

- **Definition**: queries whether the device has been activated
- **Type**: HTTP GET, XML response
- **How to call**: `http://<deviceIP>/SDK/activateStatus`; **this interface requires no authentication** — it is the only probe callable before activation
- **Example**: an integration program calls this first; if the device is not activated, it proceeds with steps ② and ③

### ② `POST /ISAPI/Security/challenge`

- **Definition**: activation challenge — the client submits its RSA public-key modulus; the device returns a random string encrypted with that key
- **Type**: HTTP POST, XML request and response
- **How to call**:
  1. Client generates a **1024-bit key pair** and extracts the public modulus (128 bytes; strip leading zeros if longer)
  2. `bytesToHexstring` the modulus → 256-byte public-key string → **Base64 encode** → embed in XML and send to the device
  3. Device Base64-decodes → `hexStringToBytes` → constructs the full public key from the modulus + fixed exponent `010001`
  4. Device generates a **32-byte hexadecimal random string**, RSA-encrypts it with the public key → `bytesToHexstring` → Base64 → replies to the client
- **Example**: `POST http://<deviceIP>/ISAPI/Security/challenge` with an XML body containing the public-key string

### ③ `PUT /ISAPI/System/activate`

- **Definition**: submits the encrypted initial password and completes activation
- **Type**: HTTP PUT, XML
- **How to call**:
  1. Client Base64-decodes the device response → `hexStringToBytes` → **RSA-decrypts with the private key** → obtains the 32-byte random string
  2. `hexStringToBytes` the random string and take its first 16 bytes as the **AES key**
  3. Encrypt "first 16 bytes of the random string + the real password" with **AES128-ECB (zero padding)** → `bytesToHexstring` → Base64 → embed in XML and send
     - Example: if the first 16 chars of the random string are `aaaabbbbccccdddd` and the password is `Abc12345`, the plaintext before encryption is `aaaabbbbccccddddAbc12345` (this proves step 2 used the random string from step 1 as the key)
  4. Device decrypts with AES, strips the first 16 bytes to recover the real password → validates it → returns the activation result
- **Alternative**: **SADP activation** — link-layer communication, **no device IP required**, only requires being under the same router; also supports LAN device discovery and password change; the HCSadpSDK integration package is provided (with a demo that doubles as a simple SADP tool)

## 3.3 Security Mechanism

### 3.3.1 Authentication

- **Definition**: all client requests must pass **Digest authentication (RFC 7616)**
- **How to call**: mainstream HTTP libraries already encapsulate it (libcurl / WebClient / HttpClient / requests); see examples in 4.1

### 3.3.2 User Permissions (Three User Types)

| User type | Permissions |
|---|---|
| Administrator (admin) | Access to all supported resources; **must remain activated at all times** |
| Operator | General resources + a few advanced resources |
| Normal user | General resources only |

### 3.3.3 Information Encryption

- The device **enables HTTPS by default**; client programs communicate with the device over HTTPS to secure transmission

## 3.4 Video Streaming

### 3.4.1 Audio/Video Streams (RTSP)

- **Definition**: devices support standard RTSP (RFC 7826); clients pull streams via RTSP; ISAPI handles getting/setting streaming parameters such as resolution, encoding format, and bitrate
- **URL format (type/addressing rule)**:
  - `rtsp://<host>[:port]/ISAPI/Streaming/channels/<ID>`
  - `:port` is optional, default **554**
  - **`<ID>` = channel number × 100 + stream type** (1 = main stream, 2 = sub stream, 3 = third stream)
- **Example**: device 172.7.203.11, channel 17 main stream → `rtsp://172.7.203.11:554/ISAPI/Streaming/channels/1701`
- Full interaction flow and messages: see 4.3

### 3.4.2 Metadata (Stream-Attached Intelligent Data)

- **Definition**: structured data produced by smart devices (face bounding boxes / face info, vehicle boxes / plate numbers, etc.) **returned in sync with the audio/video stream** over RTSP; clients can overlay it on the video
- **How to call**: enable the device's Metadata function first (some devices support subscribing by type) → then pull the stream via RTSP; the integration flow is described in the "Metadata Management" functional domain

---
# Chapter 4 — Quick Start

## 4.1 Authentication (Prerequisite for All API Calls)

- **Definition**: client requests to the device must complete **Digest authentication (RFC 7616)**; simply use library APIs
- **Demo interface**: `GET /ISAPI/System/deviceInfo` (gets device info; commonly used to verify authentication works)
- **How to call & examples (four languages)**

### C/C++ (libcurl)

```cpp
std::string strUrl = "http://192.168.18.84:80/ISAPI/System/deviceInfo";
CURL *pCurlHandle = curl_easy_init();
curl_easy_setopt(pCurlHandle, CURLOPT_CUSTOMREQUEST, "GET");
curl_easy_setopt(pCurlHandle, CURLOPT_URL, strUrl.c_str());
curl_easy_setopt(pCurlHandle, CURLOPT_USERPWD, "admin:admin12345");      // credentials
curl_easy_setopt(pCurlHandle, CURLOPT_HTTPAUTH, CURLAUTH_DIGEST);        // digest auth
curl_easy_setopt(pCurlHandle, CURLOPT_WRITEFUNCTION, OnWriteData);
curl_easy_setopt(pCurlHandle, CURLOPT_WRITEDATA, &strResponseData);
curl_easy_setopt(pCurlHandle, CURLOPT_TIMEOUT, 5);
curl_easy_setopt(pCurlHandle, CURLOPT_CONNECTTIMEOUT, 5);
CURLcode nRet = curl_easy_perform(pCurlHandle);
```

### C# (WebClient)

```csharp
string strUrl = "http://192.168.18.84:80/ISAPI/System/deviceInfo";
WebClient client = new WebClient();
client.Credentials = new NetworkCredential("admin", "admin12345");
byte[] responseData = client.DownloadData(strUrl);
string strResponseData = Encoding.UTF8.GetString(responseData);
```

### Java (HttpClient)

```java
String url = "http://192.168.18.84:80/ISAPI/System/deviceInfo";
HttpClient client = new HttpClient();
UsernamePasswordCredentials creds = new UsernamePasswordCredentials("admin", "admin12345");
client.getState().setCredentials(AuthScope.ANY, creds);
GetMethod method = new GetMethod(url);
method.setDoAuthentication(true);
int statusCode = client.executeMethod(method);
```

### Python (requests)

```python
import requests
request_url = 'http://192.168.18.84:80/ISAPI/System/deviceInfo'
auth = requests.auth.HTTPDigestAuth('admin', 'admin12345')
response = requests.get(request_url, auth=auth)
print(response.text)
```

## 4.2 Message Parsing

### 4.2.1 Four Message Formats (Types)

| Format | Content-Type | Notes |
|---|---|---|
| **XML** (default) | `application/xml; charset="UTF-8"` | Unified namespace `http://www.isapi.org/ver20/XMLSchema`, version="2.0", UTF-8 |
| **JSON** | `application/json` | **Append `?format=json` to the URL** to distinguish; without it the format is usually XML (a few exceptions — follow the interface definition), UTF-8 |
| **Binary** | `application/octet-stream` | Firmware packages, configuration files, etc. |
| **Form multipart/form-data** | `multipart/form-data; boundary=xxx` (RFC 1867) | One request carrying multiple payloads (e.g., XML person info + face image) |

- **Form essentials**: the boundary separates parts (use a long random string such as a UUID); in each part's headers, `Content-Disposition`'s **name** (mandatory) / **filename** (mandatory when the body is a file); parsers must tolerate parts **without Content-Length / Content-Type**
- **Three ways to associate a message with images**: `pid` ↔ name, `contentid` ↔ Content-ID, `filename` ↔ filename
- **Example (request)**: `POST /ISAPI/Intelligent/FDLib/pictureUpload`, with form parts `PictureUploadData` (application/xml) + `face_picture; filename="face_picture.jpg"` (image/jpeg)
- **Example (response)**: a mixed-target-detection event — a JSON part `mixedTargetDetection` (containing contentID1/2, pId1/2) + two image parts (associated via Content-ID and name)

### 4.2.2 Annotation System (The Key to Reading Interface Definitions)

Field descriptions are written as comments in the examples — `<!--...-->` for XML, `/*...*/` for JSON:

| Symbol | Meaning | Notes |
|---|---|---|
| ro / wo | read-only / write-only | ro: gettable only; wo: settable only |
| req / opt / dep | required / optional / dependent | dep: valid and required when a condition holds (e.g., `dep:and,{$.enabled,eq,true}`) |
| object / list | object / list | a list's subType is the item type |
| string / int / float | string / integer / float | range gives length or value bounds (`range:[1,32]`); also step/unit/unitType |
| bool | boolean | true / false |
| enum | enumeration | subType gives the item type; `[]` lists the options (`level1#Level 1,...`) |
| subType / desc | sub-type / description | — |

### 4.2.3 Capability Sets (capabilities)

- **Definition**: nearly every function/interface/field has a capability set, whose **URL ends with `/capabilities`** (it may take parameters, e.g., `?format=json&type=xxx`)
- **Two kinds of capabilities**:
  1. **Feature support**: `isSupportXxx` nodes (bool), with the corresponding interface URL in desc; returned in JSON or XML
  2. **Field value ranges**: `@min/@max/@opt` (JSON) or `min/max/opt/def` attributes (XML)
- **Note**: the same capability set may return different results on different models/firmware versions — **always trust what the actual device returns**

### 4.2.4 Time Format

- **ISO 8601**: `YYYY-MM-DDThh:mm:ss.sTZD`, e.g., `2017-08-16T20:17:06.123+08:00`
- **TD format recommended** (local time + offset, e.g., `...+08:00`); **TZ format** is UTC time (`...Z`)
- Older devices return TZ format with an extra `timeDiff` field for the offset — **clients must parse both TD and TZ**
- The offset changes when daylight saving time starts/ends, so **the offset alone is not a reliable timezone indicator**

### 4.2.5 Character Sets

- Single-byte: a-z, A-Z, 0-9, and 33 special symbols; multi-byte: Unicode (UTF-8, RFC 2044)
- Restricted ranges: usernames (special symbols #1–30), passwords (#1–33), UI display names (#1–15 + multi-byte text), default string fields (#1–15 + multi-byte)

### 4.2.6 Error Handling

- **Definition**: when a request fails (HTTP status code ≠ 200), the device returns an HTTP status code (RFC 2616) plus an ISAPI error code (see the document appendix)
- **Example**:

```json
HTTP/1.1 403 Forbidden
{
    "requestURL": "/ISAPI/Event/triggers/notifications/channels/whiteLightAlarm",
    "statusCode": 4,
    "statusString": "Invalid Operation",
    "subStatusCode": "notSupport",
    "errorCode": 1073741825,
    "errorMsg": "notSupport"
}
```

## 4.3 Live Preview (RTSP Streaming)

- **Definition**: pulls live audio/video streams (+Metadata) over standard RTSP (RFC 7826)
- **Stream URL (type)**: `rtsp://<host>[:port]/ISAPI/Streaming/channels/<ID>`; ID = channel × 100 + stream type; credentials can also be embedded: `rtsp://username:password@<host>/Streaming/Channels/101?transportmode=unicast`
- **How to call (six steps)**:
  1. `DESCRIBE /ISAPI/Streaming/channels/101 RTSP/1.0` — **MD5 digest authentication happens at this step** (first a 401 with `WWW-Authenticate: Digest realm=... nonce=...`, then resend with `Authorization: Digest ... response=...`)
  2. Parse the **SDP** returned by the device (`m=video ... a=control:trackID=1`, `m=audio ... a=control:trackID=2`; codecs such as H264/90000, PCMA/8000)
  3. `SETUP` per trackID (trackID=1 video, trackID=2 audio — two SETUP calls; Transport can be RTP/AVP/TCP interleaved or UDP client_port)
  4. `PLAY` → the device starts pushing the stream
  5. Receive RTP packets — **note that RTP packets may be fragmented; the client must reassemble before parsing**
  6. `TEARDOWN` to stop streaming
- **Example**: full DESCRIBE/SETUP/PLAY/TEARDOWN messages in Section 4.3.3 of the original document (including the 401 auth exchange and the complete SDP)

## 4.4 Playback

> Prerequisites: the device has storage media (SD/TF card, HDD) inserted and recording enabled. Flow: **query recordings → get playbackURI → play over RTSP**.

### ① (Optional) Calendar Query `POST /ISAPI/ContentMgmt/record/tracks/<trackStreamID>/dailyDistribution`

- **Definition**: queries which days of a month have recordings (trackStreamID = channel × 100 + stream type, e.g., 1701)
- **Type**: HTTP POST, XML
- **Example**:

```xml
Request: POST /ISAPI/ContentMgmt/record/tracks/101/dailyDistribution
<trackDailyParam><year>2021</year><monthOfYear>08</monthOfYear></trackDailyParam>

Response: <trackDailyDistribution><dayList>
  <day><id>1</id><dayOfMonth>1</dayOfMonth><record>true</record><recordType>time</recordType></day>
  ... <day>...<record>false</record></day>
</dayList></trackDailyDistribution>
```

### ② Recording Search `POST /ISAPI/ContentMgmt/search`

- **Definition**: searches recording segments by channel + time span; **parse `playbackURI` from the response to get the playback address**
- **Type**: HTTP POST, XML
- **Example**:

```xml
Request: <CMSearchDescription>
  <searchID>88C2CD4D-...</searchID>
  <trackList><trackID>101</trackID></trackList>
  <timeSpanList><timeSpan><startTime>2021-08-16T00:00:00Z</startTime>
  <endTime>2021-08-18T23:59:59Z</endTime></timeSpan></timeSpanList>
  <maxResults>100</maxResults><searchResultPostion>0</searchResultPostion>
  <metadataList><metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor></metadataList>
</CMSearchDescription>

Key response field: <playbackURI>rtsp://10.14.97.40/ISAPI/Streaming/tracks/101/?
  starttime=20210818T151815Z&endtime=20210818T151908Z&name=00000004667000100&size=1400788</playbackURI>
(plus codecType such as H.264-BP, lockStatus, metadataMatches, etc.)
```

### ③ RTSP Playback

- **How to call**: same steps as live streaming (DESCRIBE → SETUP → PLAY → TEARDOWN), **also requiring Digest authentication (computed the same way as ISAPI)**
- The playback address is the playbackURI (`/ISAPI/Streaming/tracks/<ID>/?starttime=...&endtime=...&name=...&size=...`)
- **Playback control**: `PAUSE` to pause; `PLAY` to resume; **fast/slow forward uses `PLAY` + the `Scale` header** (RFC 7826 §10.6/§12.34; the device declares supported speeds in SDP, e.g., `Scales="-1, 0.5, 0.25, ..., 2, 4"`)

## 4.5 Event Reporting (Three Receiving Methods)

> When a rule configured on the device is triggered, an event message is produced (e.g., motion detection). Comparison of the three receiving methods:

| Method | Direction | Characteristics |
|---|---|---|
| **Arming — unsubscribed** | Client GET long connection | Receives **all** events |
| **Arming — subscribed** | Client POST long connection | Receives only **listed** events |
| **Listening** | Device actively POSTs to the platform | Push address must be configured on the device; **no heartbeat messages** |

- **General arming limitations**: HTTP long connections are half-duplex — once established, the device keeps pushing events and **the client cannot send anything on this connection**; if no message (including heartbeat) arrives beyond the heartbeat interval, the client should **proactively disconnect and reconnect**

### 4.5.1.1 Unsubscribed Arming `GET /ISAPI/Event/notification/alertStream`

- **Definition**: establishes an HTTP long connection to continuously receive all device events
- **Type**: HTTP GET long connection, Digest auth, streamed response as `multipart/mixed; boundary=<frontier>`
- **How to call**: ① send the request with header `Connection: keep-alive` (resend with Authorization after the 401) → ② parse events by splitting on the boundary (each part has `Content-Type: application/xml` — **some alarms arrive as JSON; distinguish by Content-Type** — containing `<EventNotificationAlert/>`, plus image parts as `image/pjpeg`) → ③ close the connection when done
- **Example**: see Section 4.5.1.1 of the original document (401 auth → 200 `multipart/mixed` → event parts and image parts separated by `--<frontier>`)

### 4.5.1.2 Subscribed Arming `POST /ISAPI/Event/notification/subscribeEvent`

- **Definition**: establishes a long connection that receives only the events in the subscription list
- **Type**: HTTP POST long connection, response as `multipart/form-data; boundary=AaB03x`
- **How to call (seven steps)**:
  1. `GET /ISAPI/System/capabilities` to query system capabilities
  2. Check that **`isSupportSubscribeEvent`** exists and is true (false = subscription not supported)
  3. `GET /ISAPI/Event/notification/subscribeEventCap` to get the subscription capability
  4. `POST /ISAPI/Event/notification/subscribeEvent` (with header `Connection: keep-alive`) to establish the connection
  5. (Optional) Modify a subscription: first `GET /ISAPI/Event/notification/subscribeEvent/<subscribeEventID>` for the current config, then `PUT` to the same URL with changes
  6. Receive events by splitting on the boundary
  7. (Optional) Unsubscribe: `PUT /ISAPI/Event/notification/unSubscribeEvent?ID=<subscribeEventID>` (when talking to the device directly over HTTP, just close the connection — no need to call this)
- **Three kinds of data on the link**: `<SubscribeEventResponse/>` (the first form part after arming), `<EventNotificationAlert/>` (event or **heartbeat**; heartbeat has `eventType=heartBeat`), and image data
- **The device does not close the arming link on its own**, so it never sends the form terminator `--AaB03x--`
- **Example**: an ANPR event — parts `name="ANPR.xml"` (application/xml) + `name="licensePlatePicture.jpg"` (image/jpeg)

### 4.5.2 Listening (HTTP Listening Host)

- **Definition**: when an event occurs, the device **actively POSTs to a pre-configured receiving address**; the client and the event service can be the same program; **no heartbeat in listening mode**
- **Related APIs (six-step flow)**:
  1. Check support: `GET /ISAPI/Event/notification/httpHosts/capabilities` — a `<HttpHostNotificationCap>` body means supported
  2. Configure addresses:
     - All: `PUT/GET /ISAPI/Event/notification/httpHosts?security=<security>&iv=<iv>`
     - Single: `PUT/GET /ISAPI/Event/notification/httpHosts/<hostID>?security=<security>&iv=<iv>`
  3. Start a TCP listening service on the platform side (plain network programming, not covered in the document)
  4. (Optional) Connectivity test: `POST /ISAPI/Event/notification/httpHosts/<hostID>/test`
  5. Receive alarm events (two message syntaxes below)
  6. (Note) Timeouts and related parameters: `/ISAPI/Event/notification/httpHosts/<hostID>/uploadCtrl`
- **Message syntax 1 (no binary data)**: the device sends `POST <Request_URI>` with `Content-Type: application/xml` (some alarms arrive as JSON — distinguish by Content-Type), body `<EventNotificationAlert/>`; the listening host replies `200 OK` + `Connection: close`
- **Message syntax 2 (with images)**: `Content-Type: multipart/form-data; boundary=<frontier>`, with a message part (`name="Event_Type"`) and an image part (`name="Picture_Name"`, image/jpeg)
- **Error-handling example**: error code `statusCode=6 / statusString=Invalid Content / subStatusCode=eventNotSupport / errorCode=0x60001024` — **subscribed event not supported**

---

## Appendix: Chapter 2–4 API Index (Mind Map Leaf Nodes)

| API | Method | Auth | Purpose | Section |
|---|---|---|---|---|
| `/SDK/activateStatus` | GET | **None** | Query activation status | 3.2 |
| `/ISAPI/Security/challenge` | POST | No | Activation challenge (public key ↔ random string) | 3.2 |
| `/ISAPI/System/activate` | PUT | No | Set initial password, complete activation | 3.2 |
| `/ISAPI/System/deviceInfo` | GET | Digest | Device info (auth sanity check) | 4.1 |
| `rtsp://.../ISAPI/Streaming/channels/<ID>` | RTSP | Digest(MD5) | Live preview streaming | 3.4 / 4.3 |
| `/ISAPI/ContentMgmt/record/tracks/<ID>/dailyDistribution` | POST | Digest | Recording calendar query | 4.4 |
| `/ISAPI/ContentMgmt/search` | POST | Digest | Recording search (returns playbackURI) | 4.4 |
| `rtsp://.../ISAPI/Streaming/tracks/<ID>/?starttime=...` | RTSP | Digest | Playback streaming | 4.4 |
| `/ISAPI/Event/notification/alertStream` | GET | Digest | Unsubscribed arming (all events) | 4.5.1.1 |
| `/ISAPI/System/capabilities` | GET | Digest | System capabilities (incl. isSupportSubscribeEvent) | 4.5.1.2 |
| `/ISAPI/Event/notification/subscribeEventCap` | GET | Digest | Arming subscription capability | 4.5.1.2 |
| `/ISAPI/Event/notification/subscribeEvent` | POST | Digest | Establish subscribed arming connection | 4.5.1.2 |
| `/ISAPI/Event/notification/subscribeEvent/<ID>` | GET/PUT | Digest | Query/modify subscription parameters | 4.5.1.2 |
| `/ISAPI/Event/notification/unSubscribeEvent?ID=<ID>` | PUT | Digest | Cancel subscribed arming | 4.5.1.2 |
| `/ISAPI/Event/notification/httpHosts/capabilities` | GET | Digest | Listening-host capability check | 4.5.2 |
| `/ISAPI/Event/notification/httpHosts` | PUT/GET | Digest | Configure/get all listening hosts | 4.5.2 |
| `/ISAPI/Event/notification/httpHosts/<hostID>` | PUT/GET | Digest | Configure/get a single listening host | 4.5.2 |
| `/ISAPI/Event/notification/httpHosts/<hostID>/test` | POST | Digest | Listening-host connectivity test | 4.5.2 |
| `/ISAPI/Event/notification/httpHosts/<hostID>/uploadCtrl` | — | Digest | Listening timeout and related parameters | 4.5.2 |
