
import { useCallback, useEffect, useState } from "react";
import {
  Heart, Images, Search, Upload, Sparkles, CalendarDays,
  ArrowUpRight, ImagePlus, LoaderCircle, X, LogIn, UserPlus,
  LogOut, Download, UserRound, ShieldCheck, Plus, Pencil, Trash2,
} from "lucide-react";
import "./App.css";

const API = "http://localhost:8000";

async function getCsrfToken() {
  const response = await fetch(`${API}/api/auth/csrf/`, {
    credentials: "include",
  });
  if (!response.ok) throw new Error("Could not get CSRF token. Is Django running?");
  return (await response.json()).csrfToken;
}

async function postApi(url, payload, isFormData = false) {
  const csrfToken = await getCsrfToken();
  return fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      "X-CSRFToken": csrfToken,
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
    },
    body: isFormData ? payload : JSON.stringify(payload),
  });
}

async function mutateApi(url, method, payload) {
  const csrfToken = await getCsrfToken();
  return fetch(url, {
    method,
    credentials: "include",
    headers: {
      "X-CSRFToken": csrfToken,
      ...(payload === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
  });
}

function getList(data) {
  return Array.isArray(data) ? data : data.results || [];
}

function imageUrl(image) {
  if (!image) return "";
  return image.startsWith("http") ? image : `${API}${image}`;
}

function App() {
  const [photos, setPhotos] = useState([]);
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("gallery");

  const [referencePhoto, setReferencePhoto] = useState(null);
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [sceneQuery, setSceneQuery] = useState("");
  const [sceneResults, setSceneResults] = useState([]);
  const [sceneSearching, setSceneSearching] = useState(false);
  const [sceneMessage, setSceneMessage] = useState("");
  const [personReferencePhotos, setPersonReferencePhotos] = useState([null, null]);
  const [personCount, setPersonCount] = useState(2);
  const [personMomentQuery, setPersonMomentQuery] = useState("");
  const [personMomentResults, setPersonMomentResults] = useState([]);
  const [personMomentBusy, setPersonMomentBusy] = useState(false);
  const [personMomentMessage, setPersonMomentMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");

  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMessage, setAuthMessage] = useState("");

  const [savedMatches, setSavedMatches] = useState([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [savedError, setSavedError] = useState("");

  const [eventName, setEventName] = useState("");
  const [eventDescription, setEventDescription] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [editingEventId, setEditingEventId] = useState(null);
  const [adminMessage, setAdminMessage] = useState("");
  const [adminBusy, setAdminBusy] = useState(false);

  const [adminUploadEvent, setAdminUploadEvent] = useState("");
  const [adminUploadProgress, setAdminUploadProgress] = useState("");
  const [selectedAdminFiles, setSelectedAdminFiles] = useState([]);
  const [adminPhotos, setAdminPhotos] = useState([]);
  const [adminPhotoEvent, setAdminPhotoEvent] = useState("");

  const loadGallery = useCallback(async (eventId = "") => {
    setLoading(true);
    setError("");

    try {
      const query = eventId ? `?event=${encodeURIComponent(eventId)}` : "";
      const [eventsResponse, photosResponse] = await Promise.all([
        fetch(`${API}/api/events/`, { credentials: "include" }),
        fetch(`${API}/api/photos/${query}`, { credentials: "include" }),
      ]);

      if (!eventsResponse.ok || !photosResponse.ok) {
        throw new Error("Django returned an error while loading the gallery.");
      }

      const eventData = await eventsResponse.json();
      const photoData = await photosResponse.json();

      setEvents(getList(eventData));
      setPhotos(getList(photoData).map((photo) => ({
        ...photo,
        imageUrl: imageUrl(photo.image),
      })));
    } catch (err) {
      console.error(err);
      setError("Couldn't load your gallery. Check that Django is running and CORS is configured.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAdminPhotos = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/photos/`, {
        credentials: "include",
      });

      if (!response.ok) throw new Error("Could not load admin photo library.");

      const data = await response.json();
      setAdminPhotos(getList(data).map((photo) => ({
        ...photo,
        imageUrl: imageUrl(photo.image),
      })));
    } catch (err) {
      console.error(err);
      setAdminMessage(err.message || "Could not load admin photo library.");
    }
  }, []);

  const loadSavedMatches = useCallback(async () => {
    if (!user) {
      setSavedMatches([]);
      return;
    }

    setSavedLoading(true);
    setSavedError("");

    try {
      const response = await fetch(`${API}/api/search/saved-matches/`, {
        credentials: "include",
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.error || data.detail || "Saved matches could not be loaded.");
      }

      setSavedMatches(getList(data).map((item) => ({
        ...item,
        imageUrl: item.image_url || item.imageUrl,
      })));
    } catch (err) {
      setSavedError(`${err.message} We still need to add the saved-matches API in Django.`);
    } finally {
      setSavedLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadGallery();
  }, [loadGallery]);

  useEffect(() => {
    let cancelled = false;

    async function checkLogin() {
      try {
        await getCsrfToken();
        const response = await fetch(`${API}/api/auth/me/`, {
          credentials: "include",
        });
        const data = await response.json();

        if (!cancelled && data.authenticated) setUser(data);
      } catch (err) {
        console.error("Login session check failed:", err);
      } finally {
        if (!cancelled) setAuthLoading(false);
      }
    }

    checkLogin();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (user) loadSavedMatches();
    else setSavedMatches([]);
  }, [user, loadSavedMatches]);

  function chooseEvent(eventId) {
    setSelectedEvent(eventId);
    loadGallery(eventId);
  }

  function openUpload() {
    setUploadMessage("");
    setActiveTab("upload");
    document.getElementById("gallery")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  async function submitAuth(event) {
    event.preventDefault();
    setAuthMessage("");

    try {
      const isRegister = authMode === "register";
      const route = isRegister ? "register" : "login";
      const payload = isRegister
        ? { username: username.trim(), email: email.trim(), password }
        : { username: username.trim(), password };

      const response = await postApi(`${API}/api/auth/${route}/`, payload);
      const data = await response.json().catch(() => ({}));

      if (!response.ok) throw new Error(data.error || "Authentication failed.");

      setUser(data);
      setPassword("");
      setAuthMessage(isRegister ? "Account created successfully." : "Welcome back!");
      setActiveTab("gallery");
    } catch (err) {
      setAuthMessage(err.message);
    }
  }

  async function logoutUser() {
    try {
      const response = await postApi(`${API}/api/auth/logout/`, {});
      if (!response.ok) throw new Error("Logout failed.");

      setUser(null);
      setSavedMatches([]);
      setSearchResults([]);
      setActiveTab("gallery");
      setAuthMessage("You have logged out.");
    } catch (err) {
      setAuthMessage(err.message);
    }
  }

  async function uploadPhotos(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;

    if (!user) {
      setUploadMessage("Please log in before uploading photos.");
      setActiveTab("account");
      return;
    }

    if (!selectedEvent) {
      setUploadMessage("Choose a wedding event before uploading.");
      return;
    }

    setUploading(true);
    setUploadMessage("");

    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("event", selectedEvent);
        formData.append("image", file);
        formData.append("original_filename", file.name);

        const response = await postApi(`${API}/api/photos/`, formData, true);

        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || data.error || `Couldn't upload ${file.name}`);
        }
      }

      setUploadMessage(`${files.length} photo(s) uploaded successfully!`);
      await loadGallery(selectedEvent);
    } catch (err) {
      setUploadMessage(`${err.message}. Check the Django photo API.`);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function uploadAdminPhotos(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;

    if (!user?.is_admin) {
      setAdminMessage("Only admins can upload photos from the admin panel.");
      event.target.value = "";
      return;
    }

    if (!adminUploadEvent) {
      setAdminMessage("Choose an event before uploading photos.");
      event.target.value = "";
      return;
    }

    setAdminBusy(true);
    setAdminMessage("");
    setAdminUploadProgress(`Uploading 0 of ${files.length} photos...`);

    let uploaded = 0;

    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("event", adminUploadEvent);
        formData.append("image", file);
        formData.append("original_filename", file.name);

        const response = await postApi(`${API}/api/photos/`, formData, true);
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(
            data.detail || data.error ||
            `Couldn't upload ${file.name}. ${uploaded} photo(s) uploaded before the error.`
          );
        }

        uploaded += 1;
        setAdminUploadProgress(`Uploading ${uploaded} of ${files.length} photos...`);
      }

      const eventLabel = events.find(
        (item) => String(item.id) === String(adminUploadEvent)
      )?.name || "the selected event";

      setAdminMessage(`Successfully uploaded ${uploaded} photo(s) to ${eventLabel}.`);
      setSelectedEvent(adminUploadEvent);
      setSelectedAdminFiles([]);

      await Promise.all([
        loadGallery(adminUploadEvent),
        loadAdminPhotos(),
      ]);
    } catch (err) {
      setAdminMessage(`${err.message} You can retry the remaining photos.`);
      await Promise.all([
        loadGallery(adminUploadEvent),
        loadAdminPhotos(),
      ]);
    } finally {
      setAdminBusy(false);
      setAdminUploadProgress("");
      event.target.value = "";
    }
  }

  async function searchMoments(event) {
    event.preventDefault();
    const query = sceneQuery.trim();
    if (!query) {
      setSceneMessage("Describe a moment to start searching.");
      return;
    }

    setSceneSearching(true);
    setSceneMessage("");
    setSceneResults([]);

    try {
      const response = await postApi(`${API}/api/search/scene-search/`, {
        query,
        event_id: selectedEvent || null,
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.error || data.detail || "Moment search failed.");
      }

      setSceneResults((data.results || []).map((photo) => ({
        ...photo,
        imageUrl: photo.image_url || photo.imageUrl,
      })));
      setSceneMessage(
        data.results?.length
          ? `Found ${data.results.length} matching moment${data.results.length === 1 ? "" : "s"}.`
          : "No matching moments found. Try describing the scene differently."
      );
    } catch (err) {
      setSceneMessage(err.message || "Something went wrong while searching.");
    } finally {
      setSceneSearching(false);
    }
  }


  async function searchPersonMoment(event) {
    event.preventDefault();

    const selectedPeople = personReferencePhotos.slice(0, personCount);
    const missingIndex = selectedPeople.findIndex((photo) => !photo);
    if (missingIndex !== -1) {
      setPersonMomentMessage(`Choose a reference photo for Person ${missingIndex + 1}.`);
      return;
    }
    if (!personMomentQuery.trim()) {
      setPersonMomentMessage("Describe the moment you want to find.");
      return;
    }

    setPersonMomentBusy(true);
    setPersonMomentMessage("");
    setPersonMomentResults([]);

    try {
      const formData = new FormData();
      formData.append("person_count", String(personCount));
      selectedPeople.forEach((file, index) => {
        formData.append(`person_${index + 1}`, file);
      });
      formData.append("query", personMomentQuery.trim());
      if (selectedEvent) formData.append("event_id", selectedEvent);

      const response = await postApi(
        `${API}/api/search/person-moment-search/`,
        formData,
        true
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || data.detail || "Person + moment search failed.");
      }

      setPersonMomentResults((data.results || []).map((photo) => ({
        ...photo,
        imageUrl: photo.image_url || photo.imageUrl,
      })));

      setPersonMomentMessage(
        data.results?.length
          ? `Found ${data.results.length} photos containing all ${personCount} selected people.`
          : `No photos containing all ${personCount} selected people were found. Try clearer reference photos or check the event filter.`
      );
    } catch (err) {
      setPersonMomentMessage(err.message || "Search failed.");
    } finally {
      setPersonMomentBusy(false);
    }
  }

  async function findMyPhotos(event) {
    event.preventDefault();

    if (!user) {
      setAuthMessage("Please log in before searching and saving matches.");
      setActiveTab("account");
      return;
    }

    if (!referencePhoto) return;

    setSearching(true);
    setSearchResults([]);
    setUploadMessage("");

    try {
      const formData = new FormData();
      formData.append("reference_image", referencePhoto);

      if (selectedEvent) formData.append("event_id", selectedEvent);

      const response = await postApi(
        `${API}/api/search/person-search/`,
        formData,
        true
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || "Person search failed.");
      }

      setSearchResults((data.results || []).map((photo) => ({
        ...photo,
        imageUrl: photo.image_url,
      })));

      await loadSavedMatches();
      setUploadMessage(`Found ${data.results?.length || 0} matches. Matches are being saved to your account.`);
    } catch (err) {
      setUploadMessage(err.message);
    } finally {
      setSearching(false);
    }
  }

  async function downloadPhoto(photo) {
    try {
      const url = photo.imageUrl || photo.image_url;
      if (!url) throw new Error("Photo URL is unavailable.");

      const response = await fetch(url, { credentials: "include" });
      if (!response.ok) throw new Error("Could not download this photo.");

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = objectUrl;
      link.download = photo.filename || photo.original_filename || "timeloop-memory.jpg";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setUploadMessage(`${err.message} You can also open the photo in a new tab.`);
    }
  }

  function startEditEvent(event) {
    setEditingEventId(event.id);
    setEventName(event.name || "");
    setEventDescription(event.description || "");
    setEventDate(event.event_date || "");
    setAdminMessage("");

    document.getElementById("admin-dashboard")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function resetEventForm() {
    setEditingEventId(null);
    setEventName("");
    setEventDescription("");
    setEventDate("");
  }

  async function saveEvent(event) {
    event.preventDefault();

    if (!user?.is_admin) {
      setAdminMessage("Only admins can manage events.");
      return;
    }

    setAdminBusy(true);
    setAdminMessage("");

    try {
      const payload = {
        name: eventName.trim(),
        description: eventDescription.trim(),
        event_date: eventDate || null,
      };

      if (!payload.name) throw new Error("Please enter an event name.");

      const isEditing = Boolean(editingEventId);
      const response = await mutateApi(
        isEditing
          ? `${API}/api/events/${editingEventId}/`
          : `${API}/api/events/`,
        isEditing ? "PATCH" : "POST",
        payload
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || data.error || "Could not save the event.");
      }

      resetEventForm();
      setAdminMessage(isEditing ? "Event updated successfully." : "Event created successfully.");
      setSelectedEvent("");

      await Promise.all([loadGallery(""), loadAdminPhotos()]);
    } catch (err) {
      setAdminMessage(err.message);
    } finally {
      setAdminBusy(false);
    }
  }

  async function deleteEvent(event) {
    if (!user?.is_admin) return;

    if (!window.confirm(
      `Delete "${event.name}" and all photos attached to it? This cannot be undone.`
    )) return;

    setAdminBusy(true);
    setAdminMessage("");

    try {
      const response = await mutateApi(`${API}/api/events/${event.id}/`, "DELETE");

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || data.error || "Could not delete the event.");
      }

      const filter = String(selectedEvent) === String(event.id) ? "" : selectedEvent;

      if (filter === "") setSelectedEvent("");

      setAdminMessage(`"${event.name}" was deleted.`);

      await Promise.all([
        loadGallery(filter),
        loadAdminPhotos(),
      ]);
    } catch (err) {
      setAdminMessage(err.message);
    } finally {
      setAdminBusy(false);
    }
  }

  async function deletePhoto(photo) {
    if (!user?.is_admin) return;

    if (!window.confirm(
      `Delete "${photo.original_filename || "this photo"}"? This cannot be undone.`
    )) return;

    setAdminBusy(true);
    setAdminMessage("");

    try {
      const response = await mutateApi(`${API}/api/photos/${photo.id}/`, "DELETE");

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || data.error || "Could not delete the photo.");
      }

      setAdminMessage("Photo deleted successfully.");

      await Promise.all([
        loadGallery(selectedEvent),
        loadAdminPhotos(),
      ]);
    } catch (err) {
      setAdminMessage(err.message);
    } finally {
      setAdminBusy(false);
    }
  }

  const currentEvent = events.find(
    (event) => String(event.id) === String(selectedEvent)
  );

  const filteredAdminPhotos = adminPhotos.filter((photo) => {
    const photoEventId = photo.event?.id ?? photo.event;
    return !adminPhotoEvent || String(photoEventId) === String(adminPhotoEvent);
  });

  if (authLoading) {
    return (
      <div className="loading-state">
        <LoaderCircle className="spin" size={25} />
        <p>Preparing TIMELOOP...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <a className="brand" href="#login">
            <span className="brand-icon"><Heart size={19} /></span>
            <span>time<span className="brand-light">loop</span></span>
          </a>
        </header>

        <main>
          <section className="auth-section">
            <div className="auth-card">
              <div className="eyebrow">
                <Heart size={14} /> YOUR MEMORIES, YOUR ACCOUNT
              </div>

              <h1>
                {authMode === "login"
                  ? <>Welcome <em>back.</em></>
                  : <>Make it <em>personal.</em></>}
              </h1>

              <p className="section-description">
                Log in or create an account to access wedding galleries,
                find your photos, and save your memories.
              </p>

              <form className="auth-form" onSubmit={submitAuth}>
                <label>
                  Username
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                    required
                  />
                </label>

                {authMode === "register" && (
                  <label>
                    Email
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                      required
                    />
                  </label>
                )}

                <label>
                  Password
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={authMode === "register" ? "new-password" : "current-password"}
                    minLength={authMode === "register" ? 8 : undefined}
                    required
                  />
                </label>

                <button className="primary-button" type="submit">
                  {authMode === "register"
                    ? <UserPlus size={17} />
                    : <LogIn size={17} />}
                  {authMode === "register" ? "Create account" : "Log in"}
                </button>
              </form>

              {authMessage && <p className="feedback-message">{authMessage}</p>}

              <p className="auth-switch">
                {authMode === "login" ? "New to TIMELOOP?" : "Already have an account?"}{" "}
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    setAuthMode(authMode === "login" ? "register" : "login");
                    setAuthMessage("");
                  }}
                >
                  {authMode === "login" ? "Create an account" : "Log in instead"}
                </button>
              </p>
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a
          className="brand"
          href="#home"
          onClick={() => setActiveTab("gallery")}
        >
          <span className="brand-icon"><Heart size={19} /></span>
          <span>time<span className="brand-light">loop</span></span>
        </a>

        <nav className="main-nav">
          <button
            className={activeTab === "gallery" ? "nav-link active" : "nav-link"}
            onClick={() => setActiveTab("gallery")}
          >
            The Gallery
          </button>
          <button
            className={activeTab === "upload" ? "nav-link active" : "nav-link"}
            onClick={() => setActiveTab("upload")}
          >
            Share Photos
          </button>
          <button
            className={activeTab === "find" ? "nav-link active" : "nav-link"}
            onClick={() => setActiveTab("find")}
          >
            Find My Photos
          </button>
          <button
            className={activeTab === "explore" ? "nav-link active" : "nav-link"}
            onClick={() => setActiveTab("explore")}
          >
            Explore Moments
          </button>
          <button
            className={activeTab === "saved" ? "nav-link active" : "nav-link"}
            onClick={() => {
              setActiveTab("saved");
              loadSavedMatches();
            }}
          >
            My Memories
          </button>
          {user.is_admin && (
            <button
              className={activeTab === "admin" ? "nav-link active" : "nav-link"}
              onClick={() => {
                setActiveTab("admin");
                setAdminMessage("");
                setSelectedEvent("");
                setAdminPhotoEvent("");
                loadGallery("");
                loadAdminPhotos();
              }}
            >
              Admin Panel
            </button>
          )}
        </nav>

        <div className="account-actions">
          <button className="share-button" onClick={() => setActiveTab("account")}>
            <UserRound size={16} /><span>{user.username}</span>
          </button>
          <button className="outline-button" onClick={logoutUser}>
            <LogOut size={15} /> Log out
          </button>
        </div>
      </header>

      <main id="home">
        {activeTab === "account" ? (
          <section className="auth-section">
            <div className="auth-card">
              <div className="eyebrow"><Heart size={14} /> YOUR MEMORIES, YOUR ACCOUNT</div>
              <h1>Welcome <em>back.</em></h1>
              <p className="section-description">
                You are signed in as {user.username}.
              </p>
              {authMessage && <p className="feedback-message">{authMessage}</p>}
            </div>
          </section>
        ) : activeTab === "admin" && user.is_admin ? (
          <section className="admin-section" id="admin-dashboard">
            <div className="admin-heading">
              <div>
                <div className="eyebrow"><ShieldCheck size={14} /> TIMELOOP ADMINISTRATION</div>
                <h1>Manage your <em>memories.</em></h1>
                <p className="section-description">
                  Create events, organize the collection, and manage uploaded photos.
                </p>
              </div>
              <button
                className="outline-button"
                onClick={() => {
                  loadGallery("");
                  loadAdminPhotos();
                }}
                disabled={loading || adminBusy}
              >
                <Images size={16} /> Refresh data
              </button>
            </div>

            <div className="admin-stats">
              <article className="admin-stat-card">
                <span>Total events</span><strong>{events.length}</strong>
                <CalendarDays size={20} />
              </article>
              <article className="admin-stat-card">
                <span>Total photos</span><strong>{adminPhotos.length}</strong>
                <Images size={20} />
              </article>
              <article className="admin-stat-card">
                <span>Signed in as</span>
                <strong className="admin-stat-username">{user.username}</strong>
                <ShieldCheck size={20} />
              </article>
            </div>

            <div className="admin-columns">
              <section className="admin-card">
                <div className="admin-card-heading">
                  <div>
                    <div className="eyebrow">
                      {editingEventId ? "UPDATE EVENT" : "CREATE EVENT"}
                    </div>
                    <h2>{editingEventId ? "Edit an event" : "Add a new event"}</h2>
                  </div>
                  {editingEventId && (
                    <button type="button" className="text-button" onClick={resetEventForm}>
                      Cancel edit
                    </button>
                  )}
                </div>

                <form className="admin-event-form" onSubmit={saveEvent}>
                  <label>
                    Event name
                    <input
                      value={eventName}
                      onChange={(e) => setEventName(e.target.value)}
                      placeholder="e.g. Wedding Reception"
                      required
                    />
                  </label>
                  <label>
                    Description
                    <textarea
                      value={eventDescription}
                      onChange={(e) => setEventDescription(e.target.value)}
                      placeholder="Add a short description"
                      rows="3"
                    />
                  </label>
                  <label>
                    Event date
                    <input
                      type="date"
                      value={eventDate}
                      onChange={(e) => setEventDate(e.target.value)}
                    />
                  </label>
                  <button className="primary-button" type="submit" disabled={adminBusy}>
                    {adminBusy
                      ? <LoaderCircle className="spin" size={16} />
                      : editingEventId ? <Pencil size={16} /> : <Plus size={16} />}
                    {editingEventId ? "Save changes" : "Create event"}
                  </button>
                </form>
              </section>

              <section className="admin-card">
                <div className="admin-card-heading">
                  <div><div className="eyebrow">EVENT LIBRARY</div><h2>Your events</h2></div>
                  <span className="admin-count">{events.length}</span>
                </div>

                {events.length === 0 ? (
                  <p className="admin-empty">No events yet. Create your first event.</p>
                ) : (
                  <div className="admin-event-list">
                    {events.map((event) => {
                      const count = adminPhotos.filter(
                        (photo) => String(photo.event?.id ?? photo.event) === String(event.id)
                      ).length;

                      return (
                        <article className="admin-event-row" key={event.id}>
                          <div className="admin-event-info">
                            <strong>{event.name}</strong>
                            <span>
                              {event.event_date || "Date not set"} · {count} photo{count === 1 ? "" : "s"}
                            </span>
                            {event.description && <p>{event.description}</p>}
                          </div>
                          <div className="admin-row-actions">
                            <button
                              className="icon-action"
                              title="Edit event"
                              aria-label={`Edit ${event.name}`}
                              onClick={() => startEditEvent(event)}
                              disabled={adminBusy}
                            >
                              <Pencil size={15} />
                            </button>
                            <button
                              className="icon-action danger"
                              title="Delete event"
                              aria-label={`Delete ${event.name}`}
                              onClick={() => deleteEvent(event)}
                              disabled={adminBusy}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                )}
              </section>
            </div>

            <section className="admin-card admin-bulk-upload">
              <div className="admin-card-heading">
                <div>
                  <div className="eyebrow">BULK PHOTO UPLOAD</div>
                  <h2>Add photos to an event</h2>
                  <p className="section-description">
                    Choose an event and select multiple photos. Uploaded photos
                    will appear in that event's shared gallery for all logged-in users.
                  </p>
                </div>
                <Upload size={22} />
              </div>

              {events.length === 0 ? (
                <p className="admin-empty">Create an event before uploading photos.</p>
              ) : (
                <div className="admin-event-form">
                  <label>
                    Upload to event
                    <select
                      value={adminUploadEvent}
                      onChange={(e) => setAdminUploadEvent(e.target.value)}
                      required
                    >
                      <option value="">Choose an event</option>
                      {events.map((event) => (
                        <option key={event.id} value={event.id}>{event.name}</option>
                      ))}
                    </select>
                  </label>

                  <label className="admin-file-picker primary-button">
                    {adminBusy
                      ? <LoaderCircle className="spin" size={17} />
                      : <ImagePlus size={17} />}
                    {adminBusy ? "Uploading photos..." : "Choose multiple photos"}
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={(e) => {
                        setSelectedAdminFiles(Array.from(e.target.files || []));
                        uploadAdminPhotos(e);
                      }}
                      disabled={adminBusy || !adminUploadEvent}
                    />
                  </label>

                  {selectedAdminFiles.length > 0 && (
                    <div className="selected-files">
                      <strong>{selectedAdminFiles.length} photo(s) selected</strong>
                      <ul>
                        {selectedAdminFiles.slice(0, 10).map((file, index) => (
                          <li key={`${file.name}-${index}`}>{file.name}</li>
                        ))}
                      </ul>
                      {selectedAdminFiles.length > 10 &&
                        <p>And {selectedAdminFiles.length - 10} more...</p>}
                    </div>
                  )}

                  {adminUploadProgress && (
                    <p className="feedback-message">{adminUploadProgress}</p>
                  )}
                </div>
              )}
              {adminMessage && <p className="feedback-message">{adminMessage}</p>}
            </section>

            <section className="admin-card admin-photo-manager">
              <div className="admin-card-heading">
                <div>
                  <div className="eyebrow">PHOTO LIBRARY</div>
                  <h2>Manage uploaded photos</h2>
                  <p className="section-description">
                    Filter by event to manage a specific collection. Deleting a photo removes it from the shared gallery.
                  </p>
                </div>
                <span className="admin-count">{adminPhotos.length}</span>
              </div>

              <div className="admin-photo-filter">
                <label htmlFor="admin-photo-event-filter">Filter photos by event</label>
                <select
                  id="admin-photo-event-filter"
                  value={adminPhotoEvent}
                  onChange={(e) => setAdminPhotoEvent(e.target.value)}
                >
                  <option value="">All events</option>
                  {events.map((event) => (
                    <option key={event.id} value={event.id}>{event.name}</option>
                  ))}
                </select>
                <span>{filteredAdminPhotos.length} photo(s)</span>
              </div>

              {filteredAdminPhotos.length === 0 ? (
                <p className="admin-empty">No photos found for this event.</p>
              ) : (
                <div className="admin-photo-grid">
                  {filteredAdminPhotos.map((photo) => {
                    const eventId = photo.event?.id ?? photo.event;
                    const eventName = events.find(
                      (event) => String(event.id) === String(eventId)
                    )?.name || `Event ${eventId}`;

                    return (
                      <article className="admin-photo-card" key={photo.id}>
                        <div className="admin-photo-image">
                          <img
                            src={photo.imageUrl}
                            alt={photo.original_filename || "Uploaded photo"}
                            loading="lazy"
                          />
                        </div>
                        <div className="admin-photo-meta">
                          <strong title={photo.original_filename}>
                            {photo.original_filename || `Photo ${photo.id}`}
                          </strong>
                          <span>{eventName}</span>
                          <button
                            className="admin-delete-photo"
                            onClick={() => deletePhoto(photo)}
                            disabled={adminBusy}
                          >
                            <Trash2 size={14} /> Delete photo
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
              {adminMessage && <p className="feedback-message">{adminMessage}</p>}
            </section>
          </section>
        ) : (
          <>
            {activeTab !== "saved" && activeTab !== "explore" && (
              <section className="hero">
                <div className="hero-copy">
                  <div className="eyebrow"><Sparkles size={14} /> EVERY MOMENT, REMEMBERED</div>
                  <h1>Some moments<br />deserve <em>forever.</em></h1>
                  <p className="hero-description">
                    Every photograph tells a story. Discover the laughter,
                    the happy tears, and all the little moments in between.
                  </p>
                  <div className="hero-actions">
                    <button className="primary-button" onClick={() => setActiveTab("gallery")}>
                      <Images size={17} /> Explore the gallery
                    </button>
                    <button className="text-button" onClick={() => setActiveTab("find")}>
                      Find my photos <ArrowUpRight size={15} />
                    </button>
                  </div>
                  <div className="hero-note">
                    <span className="status-dot" /> A shared collection of beautiful memories
                  </div>
                </div>

                <div className="hero-visual">
                  <div className="hero-image-main">
                    <img
                      src="https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=1200&q=85"
                      alt="A couple celebrating their wedding"
                    />
                  </div>
                  <div className="image-note">
                    <Heart size={15} />
                    <div><strong>Little moments.</strong><span>Memories for a lifetime.</span></div>
                  </div>
                  <div className="hero-stamp">MOMENTS<br />THAT MATTER</div>
                </div>
              </section>
            )}

            <section className="gallery-section" id="gallery">
              {activeTab === "explore" ? (
                <section className="moment-search-section">
                  <div className="moment-search-intro">
                    <div className="eyebrow"><Sparkles size={14} /> SEARCH THE STORY, NOT JUST THE PHOTO</div>
                    <h2>Relive a <em>moment.</em></h2>
                    <p className="section-description">
                      Describe a scene, an action, or an object. TIMELOOP will look across your wedding photographs.
                    </p>
                  </div>

                  <form className="moment-search-form" onSubmit={searchMoments}>
                    <label className="moment-search-label" htmlFor="moment-query">WHAT ARE YOU LOOKING FOR?</label>
                    <div className="moment-search-input-row">
                      <Search size={19} />
                      <input
                        id="moment-query"
                        type="text"
                        value={sceneQuery}
                        onChange={(e) => setSceneQuery(e.target.value)}
                        placeholder="e.g. friends hugging and laughing"
                        maxLength={500}
                        autoComplete="off"
                      />
                      <button className="primary-button" type="submit" disabled={sceneSearching || !sceneQuery.trim()}>
                        {sceneSearching ? <LoaderCircle className="spin" size={17} /> : <Search size={17} />}
                        {sceneSearching ? "Searching..." : "Search moments"}
                      </button>
                    </div>
                    <div className="moment-search-options">
                      <label className="event-select-label">
                        <CalendarDays size={16} />
                        <select
                          value={selectedEvent}
                          onChange={(e) => setSelectedEvent(e.target.value)}
                          aria-label="Limit moment search to an event"
                        >
                          <option value="">All events</option>
                          {events.map((event) => (
                            <option key={event.id} value={event.id}>{event.name}</option>
                          ))}
                        </select>
                      </label>
                      <span>Search by people, actions, emotions or objects</span>
                    </div>
                  </form>




                  <div className="moment-suggestions">
                    <span>TRY SEARCHING</span>
                    {["People dancing", "Someone hugging the bride", "Friends laughing together", "A cat in the wedding"].map((suggestion) => (
                      <button
                        type="button"
                        className="suggestion-chip"
                        key={suggestion}
                        onClick={() => setSceneQuery(suggestion)}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>

                  {sceneMessage && (
                    <p className={sceneResults.length ? "moment-feedback" : "moment-feedback is-muted"} role="status">
                      {sceneMessage}
                    </p>
                  )}

                  {sceneSearching && (
                    <div className="loading-state moment-loading">
                      <LoaderCircle className="spin" size={25} />
                      <p>Looking through your memories...</p>
                    </div>
                  )}

                  {!sceneSearching && sceneResults.length > 0 && (
                    <div className="moment-results">
                      <div className="section-heading">
                        <div>
                          <div className="eyebrow">MATCHING PHOTOGRAPHS</div>
                          <h3>Your moments, <em>found.</em></h3>
                        </div>
                        <span className="admin-count">{sceneResults.length}</span>
                      </div>
                      <div className="photo-grid">
                        {sceneResults.map((photo, index) => (
                          <article className="photo-card" key={photo.photo_id || photo.id || index}>
                            <div className="photo-frame">
                              <img
                                src={photo.imageUrl}
                                alt={photo.filename || `Moment matching ${sceneQuery}`}
                                loading="lazy"
                              />
                            </div>
                            <div className="photo-card-caption">
                              <span>{photo.filename || photo.event_name || "Wedding memory"}</span>
                              <button className="download-button" onClick={() => downloadPhoto(photo)}>
                                <Download size={15} /> Download
                              </button>
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <section className="person-moment-panel">
                    <div className="eyebrow"><Sparkles size={14} /> PERSON + MOMENT SEARCH</div>
                    <h3>Find a moment <em>with someone.</em></h3>
                    <p className="section-description">
                      Choose 2 to 4 people. Every selected person must appear in the same photograph.
                    </p>
                    <form className="person-moment-form" onSubmit={searchPersonMoment}>
                      <label className="person-count-control">
                        How many people should be in the photo?
                        <select
                          value={personCount}
                          onChange={(e) => {
                            const nextCount = Number(e.target.value);
                            setPersonCount(nextCount);
                            setPersonReferencePhotos((current) => {
                              const next = [...current];
                              while (next.length < nextCount) next.push(null);
                              return next.slice(0, nextCount);
                            });
                            setPersonMomentResults([]);
                            setPersonMomentMessage("");
                          }}
                        >
                          <option value={2}>2 people</option>
                          <option value={3}>3 people</option>
                          <option value={4}>4 people</option>
                        </select>
                      </label>
                      <div className="person-reference-grid">
                        {Array.from({ length: personCount }, (_, index) => (
                          <label className="person-reference-upload" key={index}>
                            <span>PERSON {index + 1}</span>
                            <input
                              type="file"
                              accept="image/*"
                              onChange={(e) => {
                                const file = e.target.files?.[0] || null;
                                setPersonReferencePhotos((current) => {
                                  const next = [...current];
                                  next[index] = file;
                                  return next;
                                });
                              }}
                            />
                            <small>{personReferencePhotos[index]?.name || "Choose a clear face photo"}</small>
                          </label>
                        ))}
                      </div>
                      <input
                        type="text"
                        value={personMomentQuery}
                        onChange={(e) => setPersonMomentQuery(e.target.value)}
                        placeholder="e.g. hugging, dancing together, standing side by side"
                        maxLength={300}
                      />
                      <button
                        className="primary-button"
                        type="submit"
                        disabled={
                          personMomentBusy ||
                          personReferencePhotos.slice(0, personCount).some((photo) => !photo) ||
                          !personMomentQuery.trim()
                        }
                      >
                        {personMomentBusy ? <LoaderCircle className="spin" size={17} /> : <Search size={17} />}
                        {personMomentBusy ? "Finding your moment..." : "Find this moment"}
                      </button>
                    </form>
                    {personMomentMessage && (
                      <p className="moment-feedback" role="status">{personMomentMessage}</p>
                    )}
                    {personMomentBusy && (
                      <div className="loading-state moment-loading">
                        <LoaderCircle className="spin" size={24} />
                        <p>Checking that every selected person appears in each photo...</p>
                      </div>
                    )}
                    {!personMomentBusy && personMomentResults.length > 0 && (
                      <div className="moment-results">
                        <h4>{personMomentResults.length} photos contain all {personCount} people</h4>
                        <div className="photo-grid">
                          {personMomentResults.map((photo) => (
                            <article className="photo-card" key={photo.photo_id}>
                              <div className="photo-frame">
                                <img src={photo.imageUrl} alt={photo.filename || "Matching moment"} loading="lazy" />
                              </div>
                              <div className="photo-card-caption">
                                <span>{photo.filename || "Wedding memory"}</span>
                                <button className="download-button" onClick={() => downloadPhoto(photo)}>
                                  <Download size={15} /> Download
                                </button>
                              </div>
                              <p className="person-moment-evidence">
                                {photo.action_verified
                                  ? `Action evidence: ${photo.matched_actions.join(", ")}`
                                  : "All selected people identified. Requested action not verified by scene analysis."}
                              </p>
                            </article>
                          ))}
                        </div>
                      </div>
                    )}
                  </section>
                </section>
              ) : activeTab === "saved" ? (
                <>
                  <div className="section-heading">
                    <div>
                      <div className="eyebrow">YOUR PERSONAL COLLECTION</div>
                      <h2>My <em>memories.</em></h2>
                      <p className="section-description">
                        Your saved AI matches, ready whenever you return.
                      </p>
                    </div>
                    <button className="outline-button" onClick={loadSavedMatches}>
                      <Images size={16} /> Refresh matches
                    </button>
                  </div>

                  {savedLoading && (
                    <div className="loading-state">
                      <LoaderCircle className="spin" size={25} />
                      <p>Loading your saved memories...</p>
                    </div>
                  )}
                  {savedError && <div className="error-panel">{savedError}</div>}
                  {!savedLoading && !savedError && savedMatches.length === 0 && (
                    <div className="empty-state">
                      <Images size={32} />
                      <h3>No saved matches yet</h3>
                      <p>Use Find My Photos to search for yourself in a wedding collection.</p>
                      <button className="primary-button" onClick={() => setActiveTab("find")}>
                        <Search size={16} /> Find my photos
                      </button>
                    </div>
                  )}
                  {!savedLoading && savedMatches.length > 0 && (
                    <div className="photo-grid">
                      {savedMatches.map((photo) => (
                        <article className="photo-card" key={photo.id || photo.photo_id}>
                          <div className="photo-frame">
                            <img src={photo.imageUrl} alt={photo.filename || "Saved wedding memory"} loading="lazy" />
                          </div>
                          <div className="photo-card-caption">
                            <span>{photo.filename || "Wedding memory"}</span>
                            <button className="download-button" onClick={() => downloadPhoto(photo)}>
                              <Download size={15} /> Download
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="section-heading">
                    <div>
                      <div className="eyebrow">YOUR MEMORIES, TOGETHER</div>
                      <h2>The wedding <em>collection.</em></h2>
                      <p className="section-description">
                        One celebration, countless perspectives, all in one place.
                      </p>
                    </div>
                    <div className="gallery-controls">
                      <label className="event-select-label">
                        <CalendarDays size={16} />
                        <select
                          value={selectedEvent}
                          onChange={(e) => chooseEvent(e.target.value)}
                          aria-label="Choose wedding event"
                        >
                          <option value="">All events</option>
                          {events.map((event) => (
                            <option key={event.id} value={event.id}>{event.name}</option>
                          ))}
                        </select>
                      </label>
                      <button className="outline-button" onClick={() => setActiveTab("upload")}>
                        <Upload size={16} /> Upload
                      </button>
                    </div>
                  </div>

                  {currentEvent && (
                    <div className="event-caption">
                      <Heart size={15} /> You're viewing memories from <strong>{currentEvent.name}</strong>
                    </div>
                  )}

                  {activeTab === "upload" && (
                    <section className="action-panel">
                      <button
                        className="panel-close"
                        onClick={() => setActiveTab("gallery")}
                        aria-label="Close upload panel"
                      >
                        <X size={18} />
                      </button>
                      <ImagePlus size={25} />
                      <h3>Add your moments</h3>
                      <p>Select a wedding event first, then choose one or more photos.</p>
                      {!selectedEvent && (
                        <p className="feedback-message">Choose an event from the gallery filter first.</p>
                      )}
                      <label className="primary-button file-picker">
                        {uploading ? <LoaderCircle className="spin" size={17} /> : <Upload size={17} />}
                        {uploading ? "Uploading..." : "Choose photos"}
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          onChange={uploadPhotos}
                          disabled={uploading || !user || !selectedEvent}
                        />
                      </label>
                      {uploadMessage && <p className="feedback-message">{uploadMessage}</p>}
                    </section>
                  )}

                  {activeTab === "find" && (
                    <section className="action-panel">
                      <button
                        className="panel-close"
                        onClick={() => setActiveTab("gallery")}
                        aria-label="Close search panel"
                      >
                        <X size={18} />
                      </button>
                      <Search size={25} />
                      <h3>Find yourself in the memories</h3>
                      <p>Choose a clear photo of your face. Matching photos will be saved to your account.</p>

                      <form className="face-search-form" onSubmit={findMyPhotos}>
                        <input
                          type="file"
                          accept="image/*"
                          onChange={(e) => setReferencePhoto(e.target.files?.[0] || null)}
                          required
                        />
                        <button className="primary-button" type="submit" disabled={searching || !user}>
                          {searching ? <LoaderCircle className="spin" size={17} /> : <Search size={17} />}
                          {searching ? "Finding photos..." : "Find my photos"}
                        </button>
                      </form>

                      {uploadMessage && <p className="feedback-message">{uploadMessage}</p>}

                      {searchResults.length > 0 && (
                        <div className="search-results">
                          <h4>We found {searchResults.length} possible matches</h4>
                          <div className="photo-grid">
                            {searchResults.map((photo) => (
                              <article className="photo-card" key={photo.photo_id}>
                                <div className="photo-frame">
                                  <img src={photo.imageUrl} alt={photo.filename || "Matching wedding photo"} />
                                </div>
                                <div className="photo-card-caption">
                                  <span>{photo.filename || "Wedding memory"}</span>
                                  <button className="download-button" onClick={() => downloadPhoto(photo)}>
                                    <Download size={15} /> Download
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                          <button
                            className="outline-button"
                            onClick={() => {
                              setActiveTab("saved");
                              loadSavedMatches();
                            }}
                          >
                            View My Memories
                          </button>
                        </div>
                      )}
                    </section>
                  )}

                  {error && <div className="error-panel">{error}</div>}

                  {loading ? (
                    <div className="loading-state">
                      <LoaderCircle className="spin" size={25} />
                      <p>Gathering your memories...</p>
                    </div>
                  ) : photos.length === 0 ? (
                    <div className="empty-state">
                      <Images size={32} />
                      <h3>Your gallery is waiting</h3>
                      <p>No photos were returned for this selection. Check that your Django API has photos.</p>
                    </div>
                  ) : (
                    <div className="photo-grid">
                      {photos.map((photo, index) => (
                        <article className={`photo-card photo-card-${index % 4}`} key={photo.id}>
                          <div className="photo-frame">
                            <img
                              src={photo.imageUrl}
                              alt={photo.original_filename || "Wedding memory"}
                              loading="lazy"
                            />
                            <div className="photo-overlay"><Heart size={18} /></div>
                          </div>
                          <div className="photo-card-caption">
                            <span>{photo.original_filename || `Memory ${index + 1}`}</span>
                            <span className="photo-number">{String(index + 1).padStart(2, "0")}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}

                  {!loading && photos.length > 0 && (
                    <div className="gallery-footer">
                      <span>{photos.length} photographs in this collection</span>
                      <span>Collected with love <Heart size={13} /></span>
                    </div>
                  )}
                </>
              )}
            </section>

            {activeTab !== "saved" && (
              <section className="closing-banner">
                <div>
                  <div className="eyebrow">YOUR MOMENT BELONGS HERE</div>
                  <h2>Were you there? <em>Be part of the story.</em></h2>
                  <p>Share the photographs you captured. The smallest moments often mean the most.</p>
                </div>
                <button className="light-button" onClick={openUpload}>
                  <Upload size={17} /> Share your photos
                </button>
              </section>
            )}
          </>
        )}
      </main>

      <footer className="footer">
        <a className="brand footer-brand" href="#home" onClick={() => setActiveTab("gallery")}>
          <span className="brand-icon"><Heart size={17} /></span>
          <span>time<span className="brand-light">loop</span></span>
        </a>
        <span>Every moment has a place.</span>
        <span>Made for memories, shared by everyone.</span>
      </footer>
    </div>
  );
}

export default App;
