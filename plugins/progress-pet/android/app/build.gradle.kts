plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "ai.motchi.companion"
    compileSdk = 35
    buildFeatures { buildConfig = true }
    defaultConfig {
        applicationId = "ai.motchi.companion"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.13.0"
        buildConfigField("boolean", "COMPATIBILITY", (project.findProperty("motchiCompatibility") == "true").toString())
    }
    val signingPath = System.getenv("MOTCHI_SIGNING_FILE")
    if (signingPath != null) {
        signingConfigs.create("localRelease") {
            storeFile = file(signingPath)
            storePassword = System.getenv("MOTCHI_SIGNING_PASSWORD")
            keyAlias = "motchi"
            keyPassword = System.getenv("MOTCHI_SIGNING_PASSWORD")
        }
        buildTypes.getByName("release") { signingConfig = signingConfigs.getByName("localRelease"); isMinifyEnabled = false }
        buildTypes.getByName("debug") { signingConfig = signingConfigs.getByName("localRelease") }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
