import org.apache.nifi.processor.io.StreamCallback
import groovy.json.*
import java.nio.charset.StandardCharsets
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.auth.AWSStaticCredentialsProvider
import com.amazonaws.services.s3.AmazonS3ClientBuilder
import com.amazonaws.client.builder.AwsClientBuilder
import com.amazonaws.services.s3.model.ListObjectsV2Request

// ===== CẤU HÌNH S3 - Sử dụng NiFi Variable Registry hoặc environment =====
def ACCESS_KEY = System.getenv("S3_ACCESS_KEY") ?: ""   // Set via NiFi variable: S3_ACCESS_KEY
def SECRET_KEY = System.getenv("S3_SECRET_KEY") ?: ""  // Set via NiFi variable: S3_SECRET_KEY
def VN = TimeZone.getTimeZone("Asia/Ho_Chi_Minh")

if (!ACCESS_KEY || !SECRET_KEY) {
    log.error("[AGG] S3_ACCESS_KEY and S3_SECRET_KEY must be set as NiFi variables or environment")
    session.transfer(ff, REL_FAILURE)
    return
}

// ===== 1. Lấy FlowFile =====
def ff = session.get()
if (!ff) return

try {
    def s3Bucket   = ff.getAttribute('s3_bucket')   ?: 'traffic-data'
    // Lưu ý: Endpoint chỉ lấy IP:Port, không có http:// prefix nếu dùng SDK builder cũ, 
    // nhưng AwsClientBuilder cần full URL.
    def s3Endpoint = ff.getAttribute('s3_endpoint') ?: 'http://localhost:8333' 
    def cameraId   = ff.getAttribute('camera_id')
    def slot       = ff.getAttribute('ts_slot')

    if (!cameraId || !slot) {
        log.error("[AGG] Missing camera_id or ts_slot")
        session.transfer(ff, REL_FAILURE)
        return
    }

    // Các prefix/key
    def manifestPrefix = ff.getAttribute('s3_manifest_prefix') ?: ''
    def speedPrefix    = ff.getAttribute('s3_speed_prefix')    ?: ''
    def weatherKey     = ff.getAttribute('s3_weather_key')     ?: ''

    // ===== 2. KHỞI TẠO S3 CLIENT (Giải quyết vấn đề Auth) =====
    def creds = new BasicAWSCredentials(ACCESS_KEY, SECRET_KEY)
    def clientConfig = new AwsClientBuilder.EndpointConfiguration(s3Endpoint, "us-east-1")
    
    def s3 = AmazonS3ClientBuilder.standard()
            .withCredentials(new AWSStaticCredentialsProvider(creds))
            .withEndpointConfiguration(clientConfig)
            .withPathStyleAccessEnabled(true) // BẮT BUỘC cho SeaweedFS/MinIO
            .build()

    def jsonSlurper = new JsonSlurper()

    // ===== Helpers =====
    
    // Hàm đọc nội dung file từ S3 (Tự động Auth)
    def readS3Object = { String key ->
        try {
            if (!key || !s3.doesObjectExist(s3Bucket, key)) return null
            return s3.getObjectAsString(s3Bucket, key)
        } catch (Exception e) {
            log.warn("[AGG] Error reading ${key}: ${e.message}")
            return null
        }
    }

    // Hàm List file .json trong prefix (Tự động parse XML chuẩn)
    def listJsonKeys = { String prefix ->
        def keys = []
        if (!prefix) return keys
        try {
            def req = new ListObjectsV2Request()
                    .withBucketName(s3Bucket)
                    .withPrefix(prefix)
            
            def result = s3.listObjectsV2(req)
            // SeaweedFS có thể trả về list rỗng nếu prefix sai
            result.getObjectSummaries().each { summary ->
                if (summary.getKey().endsWith('.json')) {
                    keys << summary.getKey()
                }
            }
        } catch (Exception e) {
            log.warn("[AGG] Error listing prefix ${prefix}: ${e.message}")
        }
        return keys.sort() // Sort để đảm bảo thứ tự thời gian nếu tên file chuẩn
    }

    // Hàm đọc và merge list JSON
    def readJsonsInPrefix = { String prefix ->
        def list = []
        def keys = listJsonKeys(prefix)
        keys.each { key ->
            def txt = readS3Object(key)
            if (txt) {
                try {
                    def obj = jsonSlurper.parseText(txt)
                    if (obj instanceof List) list.addAll(obj)
                    else list << obj
                } catch (e) { log.warn("Bad JSON in ${key}") }
            }
        }
        return list
    }

    // ===== 3. XỬ LÝ LOGIC (Giữ nguyên logic của bạn) =====
    
    // 3.1 Frames
    def manifestList = readJsonsInPrefix(manifestPrefix)
    def frames = manifestList.collect { m ->
        def t = m.time ?: m.timestamp
        def imgRef = m.image_key ?: m.image_ref
        // Fix đường dẫn ảnh cho đúng chuẩn S3 URI
        if (t && imgRef) {
             // Nếu imgRef đã là full path (s3://...) thì giữ nguyên, nếu không thì ghép
            def fullPath = imgRef.startsWith("s3://") ? imgRef : "s3://${s3Bucket}/${imgRef}"
            return [time: t, image_ref: fullPath]
        }
        return null
    }.findAll { it }

    // 3.2 Speed
    def speedList = readJsonsInPrefix(speedPrefix)
    def speedSeries = speedList.collect { s ->
        def t = s.time ?: s.timestamp
        def v = s.speed
        if (v != null) {
            try { v = v.toString().toDouble() } catch (e) { v = null }
        }
        return (t && v != null) ? [time: t, speed: v] : null
    }.findAll { it }

    double avg = 0, minv = 0, maxv = 0
    if (speedSeries) {
        def vals = speedSeries*.speed
        avg  = vals.sum() / vals.size()
        minv = vals.min()
        maxv = vals.max()
    }

    // 3.3 Weather
    def weatherData = null
    if (weatherKey) {
        def txt = readS3Object(weatherKey)
        if (txt) weatherData = jsonSlurper.parseText(txt)
    }

    // ===== 4. OUTPUT =====
    def completeness = ([!frames.isEmpty(), !speedSeries.isEmpty(), (weatherData != null)].count { it } / 3.0 * 100) as int

    def aggregated = [
        camera_id    : cameraId,
        slot         : slot,
        generated_at : new Date().format("yyyy-MM-dd'T'HH:mm:ss", VN),
        frames       : frames,
        speed        : !speedSeries.isEmpty() ? [
            count   : speedSeries.size(),
            avg_kmh : Math.round(avg * 10) / 10.0,
            min_kmh : minv,
            max_kmh : maxv,
            series  : speedSeries
        ] : null,
        weather      : weatherData
    ]

    def outJson = JsonOutput.prettyPrint(JsonOutput.toJson(aggregated))

    ff = session.write(ff, { inp, outp ->
        outp.write(outJson.getBytes(StandardCharsets.UTF_8))
    } as StreamCallback)

    ff = session.putAllAttributes(ff, [
        'mime.type'        : 'application/json',
        'agg.frames'       : frames.size().toString(),
        'agg.completeness' : completeness.toString()
    ])

    session.transfer(ff, REL_SUCCESS)

} catch (Exception e) {
    log.error("[AGG] Script Failed: ${e.message}", e)
    session.transfer(ff, REL_FAILURE)
}