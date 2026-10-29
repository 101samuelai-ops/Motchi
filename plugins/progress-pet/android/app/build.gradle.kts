plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
dependencies { testImplementation("junit:junit:4.13.2") }
android {
    namespace = "ai.motchi.companion"
    compileSdk = 35
    buildFeatures { buildConfig = true }
    defaultConfig {
        applicationId = "ai.motchi.companion"
        minSdk = 26
        targetSdk = 35
        versionCode = 11
        versionName = "0.17.1"
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
