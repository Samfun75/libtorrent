/*

Copyright (c) 2014-2015, Arvid Norberg
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in
      the documentation and/or other materials provided with the distribution.
    * Neither the name of the author nor the names of its
      contributors may be used to endorse or promote products derived
      from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

*/

#include "libtorrent/session.hpp"
#include "libtorrent/session_settings.hpp"
#include "libtorrent/io_service.hpp"
#include "libtorrent/deadline_timer.hpp"
#include "libtorrent/address.hpp"
#include "libtorrent/add_torrent_params.hpp"
#include "libtorrent/time.hpp"
#include "libtorrent/settings_pack.hpp"
#include "libtorrent/ip_filter.hpp"
#include "libtorrent/alert_types.hpp"
#include <boost/bind.hpp>
#include <fstream>

#include "settings.hpp"
#include "setup_swarm.hpp"
#include "setup_transfer.hpp" // for create_torrent
#include "utils.hpp"

namespace lt = libtorrent;
using namespace sim;

namespace {

	int transfer_rate(lt::address ip)
	{
		// in order to get a heterogeneous network, the last digit in the IP
		// address determines the latency to that node as well as upload and
		// download rates.
		int last_digit;
		if (ip.is_v4())
			last_digit = ip.to_v4().to_bytes()[3];
		else
			last_digit = ip.to_v6().to_bytes()[15];
		return (last_digit + 4) * 5;
	}

} // anonymous namespace

typedef sim::chrono::high_resolution_clock::duration duration;
using sim::chrono::milliseconds;

sim::route dsl_config::incoming_route(asio::ip::address ip)
{
	int rate = transfer_rate(ip);

	auto it = m_incoming.find(ip);
	if (it != m_incoming.end()) return sim::route().append(it->second);
	it = m_incoming.insert(it, std::make_pair(ip, std::make_shared<queue>(
		std::ref(m_sim->get_io_service())
		, rate * 1000
		, lt::duration_cast<duration>(milliseconds(rate / 2))
		, 200 * 1000, "DSL modem in")));
	return sim::route().append(it->second);
}

sim::route dsl_config::outgoing_route(asio::ip::address ip)
{
	int rate = transfer_rate(ip);

	auto it = m_outgoing.find(ip);
	if (it != m_outgoing.end()) return sim::route().append(it->second);
	it = m_outgoing.insert(it, std::make_pair(ip, std::make_shared<queue>(
		std::ref(m_sim->get_io_service()), rate * 1000
		, lt::duration_cast<duration>(milliseconds(rate / 2)), 200 * 1000, "DSL modem out")));
	return sim::route().append(it->second);
}

std::string save_path(int swarm_id, int idx)
{
	char path[200];
	snprintf(path, sizeof(path), "swarm-%04d-peer-%02d"
		, swarm_id, idx);
	return path;
}

void add_extra_peers(lt::session& ses)
{
	auto handles = ses.get_torrents();
	TEST_EQUAL(handles.size(), 1);
	auto h = handles[0];

	for (int i = 0; i < 30; ++i)
	{
		char ep[30];
		snprintf(ep, sizeof(ep), "60.0.0.%d", i + 1);
		h.connect_peer(lt::tcp::endpoint(addr(ep), 6881));
	}
}

lt::torrent_status get_status(lt::session& ses)
{
	auto handles = ses.get_torrents();
	TEST_EQUAL(handles.size(), 1);
	auto h = handles[0];
	return h.status();
}

bool has_metadata(lt::session& ses)
{
	auto handles = ses.get_torrents();
	TEST_EQUAL(handles.size(), 1);
	auto h = handles[0];
	return h.status().has_metadata;
}

bool is_seed(lt::session& ses)
{
	auto handles = ses.get_torrents();
	TEST_EQUAL(handles.size(), 1);
	auto h = handles[0];
	return h.status().is_seeding;
}

int completed_pieces(lt::session& ses)
{
	auto handles = ses.get_torrents();
	TEST_EQUAL(handles.size(), 1);
	auto h = handles[0];
	return h.status().num_pieces;
}

void utp_only(lt::settings_pack& p)
{
	using namespace libtorrent;
	p.set_bool(settings_pack::enable_outgoing_tcp, false);
	p.set_bool(settings_pack::enable_incoming_tcp, false);
	p.set_bool(settings_pack::enable_outgoing_utp, true);
	p.set_bool(settings_pack::enable_incoming_utp, true);
}

void enable_enc(lt::settings_pack& p)
{
	using namespace libtorrent;
	p.set_bool(settings_pack::prefer_rc4, true);
	p.set_int(settings_pack::in_enc_policy, settings_pack::pe_forced);
	p.set_int(settings_pack::out_enc_policy, settings_pack::pe_forced);
	p.set_int(settings_pack::allowed_enc_level, settings_pack::pe_both);
}

void setup_swarm(int num_nodes
	, swarm_test type
	, std::function<void(lt::settings_pack&)> new_session
	, std::function<void(lt::add_torrent_params&)> add_torrent
	, std::function<void(lt::alert const*, lt::session&)> on_alert
	, std::function<int(int, lt::session&)> terminate)
{
	dsl_config network_cfg;
	sim::simulation sim{network_cfg};

	setup_swarm(num_nodes, type, sim, new_session
		, add_torrent, on_alert, terminate);
}

void setup_swarm(int num_nodes
	, swarm_test type
	, sim::simulation& sim
	, std::function<void(lt::settings_pack&)> new_session
	, std::function<void(lt::add_torrent_params&)> add_torrent
	, std::function<void(lt::alert const*, lt::session&)> on_alert
	, std::function<int(int, lt::session&)> terminate)
{
	lt::settings_pack pack = settings();

	lt::add_torrent_params p;
	p.flags &= ~lt::add_torrent_params::flag_paused;
	p.flags &= ~lt::add_torrent_params::flag_auto_managed;

	setup_swarm(num_nodes, type, sim, pack, p, new_session
		, add_torrent, on_alert, terminate);
}

void setup_swarm(int num_nodes
	, swarm_test type
	, sim::simulation& sim
	, lt::settings_pack const& default_settings
	, lt::add_torrent_params const& default_add_torrent
	, std::function<void(lt::settings_pack&)> new_session
	, std::function<void(lt::add_torrent_params&)> add_torrent
	, std::function<void(lt::alert const*, lt::session&)> on_alert
	, std::function<int(int, lt::session&)> terminate)
{
	setup_swarm(num_nodes, type, sim
		, default_settings
		, default_add_torrent
		, [](lt::session&) {}
		, new_session
		, add_torrent
		, on_alert
		, terminate);
}

void setup_swarm(int num_nodes
	, swarm_test type
	, sim::simulation& sim
	, lt::settings_pack const& default_settings
	, lt::add_torrent_params const& default_add_torrent
	, std::function<void(lt::session&)> init_session
	, std::function<void(lt::settings_pack&)> new_session
	, std::function<void(lt::add_torrent_params&)> add_torrent
	, std::function<void(lt::alert const*, lt::session&)> on_alert
	, std::function<int(int, lt::session&)> terminate)
{
	asio::io_service ios(sim);
	lt::time_point start_time(lt::clock_type::now());

	std::vector<boost::shared_ptr<lt::session> > nodes;
	std::vector<boost::shared_ptr<sim::asio::io_service> > io_service;
	std::vector<lt::session_proxy> zombies;
	lt::deadline_timer timer(ios);

	lt::error_code ec;
	int swarm_id = test_counter();
	std::string path = save_path(swarm_id, 0);
	lt::create_directory(path, ec);
	if (ec) fprintf(stderr, "failed to create directory: \"%s\": %s\n"
		, path.c_str(), ec.message().c_str());
	std::ofstream file(lt::combine_path(path, "temporary").c_str());
	auto ti = ::create_torrent(&file, "temporary", 0x4000, 9, false);
	file.close();

	// session 0 is the one we're testing. The others provide the scaffolding
	// it's either a downloader or a seed
	for (int i = 0; i < num_nodes; ++i)
	{
		// create a new io_service
		char ep[30];
		snprintf(ep, sizeof(ep), "50.0.%d.%d", (i + 1) >> 8, (i + 1) & 0xff);
		io_service.push_back(boost::make_shared<sim::asio::io_service>(
			boost::ref(sim), addr(ep)));

		lt::settings_pack pack = default_settings;

		// make sure the sessions have different peer ids
		lt::peer_id pid;
		std::generate(&pid[0], &pid[0] + 20, &random_byte);
		pack.set_str(lt::settings_pack::peer_fingerprint, pid.to_string());
		if (i == 0) new_session(pack);

		boost::shared_ptr<lt::session> ses =
			boost::make_shared<lt::session>(pack
				, boost::ref(*io_service.back()));
		init_session(*ses);
		nodes.push_back(ses);

		if (i > 0)
		{
			// the other sessions should not talk to each other
			lt::ip_filter filter;
			filter.add_rule(addr("0.0.0.0"), addr("255.255.255.255"), lt::ip_filter::blocked);
			filter.add_rule(addr("50.0.0.1"), addr("50.0.0.1"), 0);
			ses->set_ip_filter(filter);
		}

		lt::add_torrent_params p = default_add_torrent;
		if (type == swarm_test::download)
		{
			// in download tests, session 0 is a downloader and every other session
			// is a seed. save path 0 is where the files are, so that's for seeds
			p.save_path = save_path(swarm_id, i > 0 ? 0 : 1);
		}
		else
		{
			// in seed tests, session 0 is a seed and every other session
			// a downloader. save path 0 is where the files are, so that's for seeds
			p.save_path = save_path(swarm_id, i);
		}
		p.ti = ti;
		if (i == 0) add_torrent(p);
		ses->async_add_torrent(p);

		ses->set_alert_notify([&, i]() {
			// this function is called inside libtorrent and we cannot perform work
			// immediately in it. We have to notify the outside to pull all the alerts
			io_service[i]->post([&,i]()
			{
				lt::session* ses = nodes[i].get();

				// when shutting down, we may have destructed the session
				if (ses == nullptr) return;

				std::vector<lt::alert*> alerts;
				ses->pop_alerts(&alerts);

				// to debug the sessions not under test, comment out the following
				// line
				if (i != 0) return;

				for (lt::alert* a : alerts)
				{

					// only print alerts from the session under test
					lt::time_duration d = a->timestamp() - start_time;
					boost::uint32_t millis = lt::duration_cast<lt::milliseconds>(d).count();
					printf("%4d.%03d: %-25s %s\n", millis / 1000, millis % 1000
						, a->what()
						, a->message().c_str());

					// if a torrent was added save the torrent handle
					if (lt::add_torrent_alert* at = lt::alert_cast<lt::add_torrent_alert>(a))
					{
						lt::torrent_handle h = at->handle;

						// now, connect this torrent to all the others in the swarm
						// start at 1 to avoid self-connects
						for (int k = 1; k < num_nodes; ++k)
						{
							// TODO: the pattern of creating an address from a format
							// string and an integer is common. It should probably be
							// factored out into its own function
							char ep[30];
							snprintf(ep, sizeof(ep), "50.0.%d.%d", (k + 1) >> 8, (k + 1) & 0xff);
							h.connect_peer(lt::tcp::endpoint(addr(ep), 6881));
						}
					}

					on_alert(a, *ses);
				}
			});
		});
	}

	int tick = 0;
	std::function<void(lt::error_code const&)> on_tick
		= [&](lt::error_code const& ec)
	{
		if (ec) return;

		bool shut_down = terminate(tick, *nodes[0]);

		if (type == swarm_test::upload)
		{
			shut_down |= std::all_of(nodes.begin() + 1, nodes.end()
				, [](boost::shared_ptr<lt::session> const& s)
				{ return is_seed(*s); });

			if (tick > 70 * (num_nodes - 1) && !shut_down)
			{
				TEST_ERROR("seeding failed!");
			}
		}

		if (shut_down)
		{
			printf("TERMINATING\n");

			// terminate simulation
			for (int i = 0; i < int(nodes.size()); ++i)
			{
				zombies.push_back(nodes[i]->abort());
				nodes[i].reset();
			}
			return;
		}

		++tick;

		timer.expires_from_now(lt::seconds(1));
		timer.async_wait(on_tick);
	};

	timer.expires_from_now(lt::seconds(1));
	timer.async_wait(on_tick);

	sim.run();
}
