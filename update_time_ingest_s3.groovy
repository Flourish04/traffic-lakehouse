import java.nio.charset.StandardCharsets
import java.text.SimpleDateFormat
import java.util.Locale

/**
 * NiFi ExecuteGroovyScript - INGEST Flow
 * Tính slot 5 phút và tạo S3 paths
 * 
 * Input attributes: camera_id, Date (header từ API)
 * Output attributes: S3 paths cho PutS3Object
 */

def flowFile = session.get()
if (flowFile == null) return

// ===== CONFIG =====
def VN = TimeZone.getTimeZone("Asia/Ho_Chi_Minh")
def s3Bucket = "traffic-data"
def s3Endpoint = System.getenv("S3_ENDPOINT") ?: "http://localhost:8333"

// Lấy camera_id
def cameraId = flowFile.getAttribute("camera_id")
if (cameraId == null || cameraId.trim().isEmpty()) {
    log.error("camera_id is missing on flowfile")
    session.transfer(flowFile, REL_FAILURE)
    return
}

// ===== PARSE DATE HEADER =====
def dateHeader = flowFile.getAttribute("Date")
long nowMs

if (dateHeader != null && !dateHeader.trim().isEmpty()) {
    try {
        def sdf = new SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss z", Locale.ENGLISH)
        def parsed = sdf.parse(dateHeader)
        nowMs = parsed.getTime()
    } catch (Exception e) {
        log.warn("Cannot parse Date header '${dateHeader}', fallback to system time: ${e.message}")
        nowMs = System.currentTimeMillis()
    }
} else {
    nowMs = System.currentTimeMillis()
}

// ===== TÍNH SLOT 5 PHÚT =====
long slotMs = nowMs - (nowMs % 300000L)

def slotDate = new Date(slotMs)
def nowDate = new Date(nowMs)

// Formats (UTC+7)
def date = slotDate.format("yyyy-MM-dd", VN)
def tsSlot = slotDate.format("yyyy-MM-dd'T'HH:mm:00", VN)   // Slot time (chuẩn ISO 8601)
def frameTime = nowDate.format("yyyy-MM-dd'T'HH:mm:ss", VN) // Frame time

// ===== S3 PATHS =====
// Latest (overwrite)
def latestKey = "latest/${cameraId}.jpg"

// Raw image (append - mỗi frame 1 file)
def rawImageKey = "raw/dt=${date}/images/${cameraId}_${frameTime}.jpg"

// Raw weather (1 per slot - overwrite trong slot)
def rawWeatherKey = "raw/dt=${date}/weather/${cameraId}_${tsSlot}.json"

// Raw speed (gom theo slot folder - dễ list)
def rawSpeedKey = "raw/dt=${date}/speed/${cameraId}/${tsSlot}/${cameraId}_${frameTime}.json"

// Manifest (giữ cấu trúc cũ: nhiều files per slot)
def manifestKey = "manifest/dt=${date}/${cameraId}/${tsSlot}/${cameraId}_${frameTime}.json"

// Batch output
def batchKey = "batch/dt=${date}/${cameraId}_${tsSlot}.json"

// Image reference cho manifest JSON
def imageRef = "s3://${s3Bucket}/${rawImageKey}"

// ===== SET ATTRIBUTES =====
flowFile = session.putAttribute(flowFile, "s3_bucket", s3Bucket)
flowFile = session.putAttribute(flowFile, "s3_endpoint", s3Endpoint)

// Time attributes
flowFile = session.putAttribute(flowFile, "date", date)
flowFile = session.putAttribute(flowFile, "slot_epoch_ms", String.valueOf(slotMs))
flowFile = session.putAttribute(flowFile, "ts_slot", tsSlot)
flowFile = session.putAttribute(flowFile, "frame_time", frameTime)

// S3 keys
flowFile = session.putAttribute(flowFile, "s3_latest_key", latestKey)
flowFile = session.putAttribute(flowFile, "s3_raw_image_key", rawImageKey)
flowFile = session.putAttribute(flowFile, "s3_raw_weather_key", rawWeatherKey)
flowFile = session.putAttribute(flowFile, "s3_raw_speed_key", rawSpeedKey)
flowFile = session.putAttribute(flowFile, "s3_manifest_key", manifestKey)
flowFile = session.putAttribute(flowFile, "s3_batch_key", batchKey)

// For manifest JSON content
flowFile = session.putAttribute(flowFile, "image_ref", imageRef)

session.transfer(flowFile, REL_SUCCESS)
