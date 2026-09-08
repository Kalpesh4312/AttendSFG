/**
 * Reliable browser geolocation helper.
 *
 * Strategy:
 * 1. Try a normal/cached location first.
 * 2. If that fails, try high-accuracy GPS.
 * 3. Give mobile devices enough time to obtain a GPS fix.
 */

function getCurrentPosition(options = {}) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported by this browser."));
      return;
    }

    const defaultOptions = {
      enableHighAccuracy: false,
      timeout: 30000,
      maximumAge: 60000,
    };

    const finalOptions = {
      ...defaultOptions,
      ...options,
    };

    console.log("[geo] Starting location request", finalOptions);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        console.log("[geo] Location obtained:", {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });

        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });
      },

      (err) => {
        console.warn("[geo] First location attempt failed:", {
          code: err.code,
          message: err.message,
        });

        // If the normal provider times out, try high-accuracy GPS.
        if (err.code === 3 && !finalOptions.enableHighAccuracy) {
          console.log("[geo] Retrying with high accuracy...");

          navigator.geolocation.getCurrentPosition(
            (pos) => {
              console.log("[geo] High-accuracy location obtained:", {
                latitude: pos.coords.latitude,
                longitude: pos.coords.longitude,
                accuracy: pos.coords.accuracy,
              });

              resolve({
                latitude: pos.coords.latitude,
                longitude: pos.coords.longitude,
                accuracy: pos.coords.accuracy,
              });
            },

            (retryErr) => {
              console.error("[geo] High-accuracy attempt failed:", {
                code: retryErr.code,
                message: retryErr.message,
              });

              reject(new Error(mapGeoError(retryErr)));
            },

            {
              enableHighAccuracy: true,
              timeout: 30000,
              maximumAge: 0,
            }
          );

          return;
        }

        reject(new Error(mapGeoError(err)));
      },

      finalOptions
    );
  });
}

function mapGeoError(err) {
  switch (err.code) {
    case 1:
      return "Location access was denied. Please allow location access for this website in your browser settings.";

    case 2:
      return "Location information is unavailable. Please turn on GPS/location services and try again.";

    case 3:
      return "Timed out while getting your location. Turn on GPS/location services, move near a window or outdoors, and try again.";

    default:
      return "Could not determine your location. Please check your phone's location settings.";
  }
}