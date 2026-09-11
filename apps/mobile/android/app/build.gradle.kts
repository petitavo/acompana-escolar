plugins {
    id("com.android.application")
    id("kotlin-android")
    id("org.jetbrains.kotlin.kapt")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    buildFeatures { buildConfig = true }
    namespace = "pe.upc.acompana.acompana_escolar"
    compileSdk = 36
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        // Stable application ID preserves installations and encrypted local data.
        applicationId = "pe.upc.acompana.acompana_escolar"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        for (key in listOf("FIREBASE_APP_ID", "FIREBASE_API_KEY", "FIREBASE_PROJECT_ID", "FIREBASE_SENDER_ID")) {
            val value = (System.getenv(key) ?: "").replace("\\", "\\\\").replace("\"", "\\\"")
            buildConfigField("String", key, "\"$value\"")
        }
        minSdk = 29
        targetSdk = 36
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        val storePath = System.getenv("ANDROID_KEYSTORE_FILE")
        if (!storePath.isNullOrBlank()) {
            create("institution") {
                storeFile = file(storePath)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.findByName("institution")
            // With no institutional key the release output stays unsigned.
            // Never reuse the development key for a published release.
        }
    }
}

flutter {
    source = "../.."
}


dependencies {
    implementation("com.google.firebase:firebase-messaging:25.0.0")
    implementation("com.google.android.gms:play-services-location:21.3.0")
    testImplementation("org.json:json:20250517")
    implementation("androidx.room:room-runtime:2.7.2")
    kapt("androidx.room:room-compiler:2.7.2")
    implementation("androidx.work:work-runtime-ktx:2.10.3")
    implementation("net.zetetic:sqlcipher-android:4.10.0@aar")
    implementation("androidx.sqlite:sqlite-ktx:2.5.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    testImplementation("junit:junit:4.13.2")
}
