package com.nonpolynomial.intiface_central

import android.app.Application
import io.flutter.embedding.android.FlutterActivity
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * A very naive smoke test for [MainActivity].
 *
 * A full launch of a [FlutterActivity] can't run on the host JVM: [MainActivity]'s
 * init block loads the "rust_lib_intiface_central" native library, and the Flutter
 * engine itself needs native code. Those .so files are Android (ARM) binaries and
 * aren't loadable off-device. So this test checks the two things that *are*
 * meaningful on the host: the activity is a proper [FlutterActivity], and launching
 * it actually executes the activity's startup path (reaching the native boundary)
 * rather than failing earlier for some other reason.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = Application::class)
class MainActivitySmokeTest {

  @Test
  fun mainActivityIsAFlutterActivity() {
    assertTrue(
      "MainActivity must be a FlutterActivity to be launchable by the Flutter embedding",
      FlutterActivity::class.java.isAssignableFrom(MainActivity::class.java),
    )
  }

  @Test
  fun mainActivityLaunchExecutesStartupPath() {
    try {
      // On a host JVM, constructing MainActivity runs its init block, which calls
      // System.loadLibrary("rust_lib_intiface_central"). That library isn't host
      // loadable, so we expect an UnsatisfiedLinkError for exactly that library —
      // proving the activity class resolves and its launch path runs. If the lib
      // ever is loadable on host, we instead confirm it launched without finishing.
      val activity = Robolectric.buildActivity(MainActivity::class.java).create().get()
      assertNotNull(activity)
      assertFalse("MainActivity should not finish immediately on launch", activity.isFinishing)
    } catch (e: UnsatisfiedLinkError) {
      assertTrue(
        "Launch should only be blocked on host by the native library load, but got: ${e.message}",
        e.message?.contains("rust_lib_intiface_central") == true,
      )
    }
  }
}
