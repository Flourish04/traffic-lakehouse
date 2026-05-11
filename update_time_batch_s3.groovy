import java.nio.charset.StandardCharsets

/**
 * NiFi ExecuteGroovyScript - BATCH Flow Preparation
 * Tính slot 5 phút TRƯỚC và tạo S3 paths cho batch processing
 * 
 * Input attributes: camera_id
 * Output attributes: S3 paths/prefixes cho ListS3, FetchS3
 */

def flowFile = session.get()
if (flowFile == null) return

// ===== CONFIG =====
// S3 endpoint: dùng env var hoặc NiFi variable; fallback localhost cho dev local
def s3Bucket = "traffic-data"
def s3Endpoint = System.getenv("S3_ENDPOINT") ?: "http://localhost:8333"

// Lấy camera_id
def cameraId = flowFile.getAttribute("camera_id")
if (cameraId == null || cameraId.trim().isEmpty()) {
    log.error("camera_id is missing on flowfile")
    session.transfer(flowFile, REL_FAILURE)
    return
}

// ===== TÍNH SLOT 5 PHÚT TRƯỚC =====
// Batch xử lý slot đã hoàn thành (slot trước)
def VN = TimeZone.getTimeZone("Asia/Ho_Chi_Minh")
long nowMs = System.currentTimeMillis()
long slotSize = 300000L  // 5 phút

// (now - 5p) để lấy slot trước
long slotIndex = (nowMs - slotSize) / slotSize
long slotEpochMs = slotIndex * slotSize

def slotDate = new Date(slotEpochMs)

// Formats (UTC+7)
def date = slotDate.format("yyyy-MM-dd", VN)
def tsSlot = slotDate.format("yyyy-MM-dd'T'HH:mm:00", VN)   // Slot time (giữ nguyên :)

// ===== S3 PATHS/PREFIXES =====
// Manifest prefix (để ListS3 scan folder)
def manifestPrefix = "manifest/dt=${date}/${cameraId}/${tsSlot}/"

// Weather file (1 file per slot)
def weatherKey = "raw/dt=${date}/weather/${cameraId}_${tsSlot}.json"

// Speed prefix (gom theo slot folder - chỉ cần list prefix)
def speedPrefix = "raw/dt=${date}/speed/${cameraId}/${tsSlot}/"

// Batch output
def batchKey = "batch/dt=${date}/${cameraId}_${tsSlot}.json"

// ===== SET ATTRIBUTES =====
flowFile = session.putAttribute(flowFile, "s3_bucket", s3Bucket)
flowFile = session.putAttribute(flowFile, "s3_endpoint", s3Endpoint)

// Time attributes
flowFile = session.putAttribute(flowFile, "date", date)
flowFile = session.putAttribute(flowFile, "slot_epoch_ms", String.valueOf(slotEpochMs))
flowFile = session.putAttribute(flowFile, "ts_slot", tsSlot)

// S3 paths for batch processing
flowFile = session.putAttribute(flowFile, "s3_manifest_prefix", manifestPrefix)
flowFile = session.putAttribute(flowFile, "s3_weather_key", weatherKey)
flowFile = session.putAttribute(flowFile, "s3_speed_prefix", speedPrefix)
flowFile = session.putAttribute(flowFile, "s3_batch_key", batchKey)

session.transfer(flowFile, REL_SUCCESS)
